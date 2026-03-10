import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Analítico", layout="wide")

@st.cache_data
def carregar_dados(file):
    try:
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names
        
        # Mapeamento inteligente de abas
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Limpeza e padronização
        for df in [df_turnover, df_admitidos, df_af_raw]:
            df.columns = df.columns.str.strip().str.lower()

        # Mapeamento de colunas de afastamento
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)
        c_emp = next((c for c in cols_af if 'empresa' in c or 'unidade' in c), None)

        # Conversão de datas e números
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        # Taxa de Turnover
        df_turnover['turnover_taxa'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / df_turnover['colaboradores'].replace(0, 1)) * 100

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot, c_emp)
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return None

# --- 2. IMPORTAÇÃO ---
st.sidebar.header("📁 Base de Dados")
arquivo_subido = st.sidebar.file_uploader("Suba o arquivo BI_RH.xlsx", type=["xlsx"])

if arquivo_subido:
    dados = carregar_dados(arquivo_subido)
    if dados:
        df_t, df_a, df_af, (c_ini, c_fim, c_mot, c_emp_af) = dados

        # --- 3. FILTROS ---
        ano_sel = st.sidebar.selectbox("Selecione o Ano", sorted(df_t['ano'].unique(), reverse=True))
        df_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel = st.sidebar.selectbox("Selecione o Mês", df_meses['mes_nome'].unique())

        # Dados do mês selecionado e anterior (Delta)
        data_atual = df_meses[df_meses['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        data_ant = data_atual - pd.DateOffset(months=1)
        df_atual = df_t[df_t['mês_ano'] == data_atual].iloc[0]
        df_ant_list = df_t[df_t['mês_ano'] == data_ant]
        df_ant = df_ant_list.iloc[0] if not df_ant_list.empty else None

        # --- 4. DASHBOARD ---
        st.title(f"📊 Dashboard RH - {mes_sel}/{ano_sel}")

        # KPIs superiores
        c1, c2, c3, c4 = st.columns(4)
        def get_delta(val_at, col): return (val_at - df_ant[col]) if df_ant is not None else 0

        c1.metric("Efetivo", int(df_atual['colaboradores']), delta=int(get_delta(df_atual['colaboradores'], 'colaboradores')))
        c2.metric("Admissões", int(df_atual['admissões']), delta=int(get_delta(df_atual['admissões'], 'admissões')))
        c3.metric("Desligamentos", int(df_atual['desligamentos']), delta=int(get_delta(df_atual['desligamentos'], 'desligamentos')), delta_color="inverse")
        c4.metric("Turnover", f"{df_atual['turnover_taxa']:.2f}%", delta=f"{get_delta(df_atual['turnover_taxa'], 'turnover_taxa'):.2f}%", delta_color="inverse")

        st.markdown("---")

        # --- 5. GRÁFICO DE TENDÊNCIA COM RÓTULOS ---
        st.subheader("📈 Evolução Mensal (Movimentação vs Efetivo)")
        df_plot = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        
        fig_evol = go.Figure()
        # Admissões com rótulo superior
        fig_evol.add_trace(go.Bar(x=df_plot['mes_nome'], y=df_plot['admissões'], name='Admissões', marker_color='#2ecc71',
                                 text=df_plot['admissões'], textposition='outside'))
        
        # Desligamentos com rótulo superior
        fig_evol.add_trace(go.Bar(x=df_plot['mes_nome'], y=df_plot['desligamentos'], name='Desligamentos', marker_color='#e74c3c',
                                 text=df_plot['desligamentos'], textposition='outside'))
        
        # Efetivo (Linha) com rótulo superior
        fig_evol.add_trace(go.Scatter(x=df_plot['mes_nome'], y=df_plot['colaboradores'], name='Efetivo', yaxis='y2',
                                     line=dict(color='#3498db', width=3), mode='lines+markers+text',
                                     text=df_plot['colaboradores'], textposition='top center'))

        fig_evol.update_layout(yaxis=dict(title="Movimentações"), yaxis2=dict(title="Efetivo", overlaying='y', side='right'),
                              barmode='group', legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig_evol, use_container_width=True)

        # --- 6. SEÇÃO DE AFASTAMENTOS ---
        st.markdown("---")
        col_af1, col_af2 = st.columns([1, 2]) # Coluna da esquerda menor para o destaque numérico

        # Filtragem de afastados
        fim_mes = data_atual + pd.offsets.MonthEnd(0)
        mask = (df_af[c_ini] <= fim_mes) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_atual))
        df_af_mes = df_af[mask]

        with col_af1:
            st.subheader("🥪 Resumo de Afastamentos")
            # Destaque para a QUANTIDADE TOTAL de afastados
            st.metric("Total de Colaboradores Afastados", len(df_af_mes))
            st.write("Este número representa todos os colaboradores que tiveram afastamento ativo em algum momento deste mês.")

        with col_af2:
            st.subheader("Motivos Frequentes")
            if not df_af_mes.empty:
                resumo = df_af_mes[c_mot].value_counts().reset_index()
                # Gráfico de barras horizontais com rótulo de dados
                fig_af = px.bar(resumo, x='count', y=c_mot, orientation='h', 
                               text='count', # Define o rótulo como o próprio valor da contagem
                               color_discrete_sequence=['#9b59b6'])
                fig_af.update_traces(textposition='outside') # Coloca o rótulo fora da barra
                st.plotly_chart(fig_af, use_container_width=True)
            else:
                st.info("Nenhum registro de afastamento para este mês.")

        # Rodapé de detalhes
        with st.expander("📋 Lista de Afastados do Mês"):
            st.dataframe(df_af_mes[[c_ini, c_fim, c_mot]].sort_values(c_ini), use_container_width=True)

else:
    st.info("Aguardando arquivo para gerar os indicadores...")
