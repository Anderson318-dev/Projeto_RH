import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados(file):
    try:
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names
        
        # Localização automática das abas
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Padronização de colunas para evitar erros de digitação
        for df in [df_turnover, df_admitidos, df_af_raw]:
            df.columns = df.columns.str.strip().str.lower()

        # Mapeamento de colunas de Afastamento
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)

        # --- TRATAMENTO DE DATAS (O SEGREDO DO DELTA) ---
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        
        # Criamos uma coluna de 'PERÍODO' que ignora se o dia é 01 ou 31
        df_turnover['periodo'] = df_turnover['mês_ano'].dt.to_period('M')
        
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        # CÁLCULOS DE TAXAS
        df_turnover['turnover_taxa'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / 
                                        df_turnover['colaboradores'].replace(0, 1)) * 100
        
        df_turnover['retencao_taxa'] = (df_turnover['desligamentos'] / 
                                        df_turnover['colaboradores'].replace(0, 1)) * 100

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot)
    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None

# --- 2. INTERFACE ---
st.sidebar.header("📁 Importação")
arquivo_subido = st.sidebar.file_uploader("Selecione o BI_RH.xlsx", type=["xlsx"])

if arquivo_subido:
    dados = carregar_dados(arquivo_subido)
    if dados:
        df_t, df_a, df_af, (c_ini, c_fim, c_mot) = dados

        ano_sel = st.sidebar.selectbox("Ano", sorted(df_t['ano'].unique(), reverse=True))
        df_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel = st.sidebar.selectbox("Mês", df_meses['mes_nome'].unique())

        # --- 3. LÓGICA DE COMPARAÇÃO (MESMO COM ÚLTIMO DIA DO MÊS) ---
        # Pegamos o período (Ano-Mês) da seleção atual
        data_sel = df_meses[df_meses['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        per_atual = data_sel.to_period('M')
        # Calculamos o período anterior voltando 1 mês
        per_anterior = (data_sel - pd.DateOffset(months=1)).to_period('M')

        # Localizamos as linhas correspondentes
        row_atual = df_t[df_t['periodo'] == per_atual].iloc[0]
        row_ant_list = df_t[df_t['periodo'] == per_anterior]
        row_ant = row_ant_list.iloc[0] if not row_ant_list.empty else None

        # --- 4. KPIs (5 COLUNAS NO TOPO) ---
        st.title(f"📊 INDICADDORES RH - {mes_sel}/{ano_sel}")
        
        # Função para calcular o delta (variação)
        def calc_delta(val_atual, col):
            return (val_atual - row_ant[col]) if row_ant is not None else None

        # Mensagem de ajuda unificada
        msg_ajuda = "Comparação com o mês anterior. 🔼/🔽 indicam a direção. Cores: Verde (Melhora) e Vermelho (Atenção)."

        c1, c2, c3, c4, c5 = st.columns(5)
        
        c1.metric("Efetivo", int(row_atual['colaboradores']), 
                  delta=calc_delta(row_atual['colaboradores'], 'colaboradores'), help=msg_ajuda)
        
        c2.metric("Admissões", int(row_atual['admissões']), 
                  delta=calc_delta(row_atual['admissões'], 'admissões'), help=msg_ajuda)
        
        c3.metric("Desligamentos", int(row_atual['desligamentos']), 
                  delta=calc_delta(row_atual['desligamentos'], 'desligamentos'), 
                  delta_color="inverse", help=msg_ajuda)
        
        c4.metric("Taxa Turnover", f"{row_atual['turnover_taxa']:.2f}%", 
                  delta=f"{calc_delta(row_atual['turnover_taxa'], 'turnover_taxa'):.2f}%" if row_ant is not None else None, 
                  delta_color="inverse", help=msg_ajuda)
        
        c5.metric("Taxa Retenção", f"{row_atual['retencao_taxa']:.2f}%", 
                  delta=f"{calc_delta(row_atual['retencao_taxa'], 'retencao_taxa'):.2f}%" if row_ant is not None else None, 
                  delta_color="inverse", help=msg_ajuda)

        st.markdown("---")

        # --- 5. GRÁFICOS (COM RÓTULOS SUPERIORES) ---
        st.subheader("📈 Evolução da Movimentação Mensal")
        df_ano_plot = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_ano_plot['mes_nome'], y=df_ano_plot['admissões'], name='Admissões', 
                             marker_color='#2ecc71', text=df_ano_plot['admissões'], textposition='outside'))
        
        fig.add_trace(go.Bar(x=df_ano_plot['mes_nome'], y=df_ano_plot['desligamentos'], name='Desligamentos', 
                             marker_color='#e74c3c', text=df_ano_plot['desligamentos'], textposition='outside'))
        
        fig.add_trace(go.Scatter(x=df_ano_plot['mes_nome'], y=df_ano_plot['colaboradores'], name='Efetivo Total', 
                                 yaxis='y2', line=dict(color='#3498db', width=4), mode='lines+markers+text',
                                 text=df_ano_plot['colaboradores'].astype(int), textposition='top center'))

        fig.update_layout(
            yaxis=dict(title="Volume"),
            yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
            barmode='group',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- 6. AFASTAMENTOS ---
        st.markdown("---")
        col_af1, col_af2 = st.columns([1, 2])
        
        # Filtro de afastados usando o fim do mês selecionado
        data_fim_mes = data_sel + pd.offsets.MonthEnd(0)
        mask = (df_af[c_ini] <= data_fim_mes) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_sel))
        df_af_mes = df_af[mask]

        with col_af1:
            st.subheader("📋 Absenteísmo")
            st.metric("Total de Afastados no Mês", len(df_af_mes))
            st.info("Colaboradores que estiveram afastados durante o mês de referência.")

        with col_af2:
            st.subheader("Motivos de Afastamento")
            if not df_af_mes.empty:
                resumo = df_af_mes[c_mot].value_counts().reset_index()
                fig_af = px.bar(resumo, x='count', y=c_mot, orientation='h', text='count', color_discrete_sequence=['#34495e'])
                fig_af.update_traces(textposition='outside')
                st.plotly_chart(fig_af, use_container_width=True)
            else:
                st.write("Sem registros para este período.")

        with st.expander("Lista detalhada de afastados"):
            st.dataframe(df_af_mes, use_container_width=True)
else:
    st.info("Importe o BI_RH.xlsx para visualizar os indicadores.")
