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
        
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        for df in [df_turnover, df_admitidos, df_af_raw]:
            df.columns = df.columns.str.strip().str.lower()

        # Mapeamento de colunas de Afastamento
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)

        # Tratamento de Datas e Números
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        # CÁLCULOS DE TAXAS
        # Turnover: ((Adm + Desl) / 2) / Colaboradores
        df_turnover['turnover_taxa'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / 
                                        df_turnover['colaboradores'].replace(0, 1)) * 100
        
        # Retenção: Desligamentos / Colaboradores (conforme solicitado)
        df_turnover['retencao_taxa'] = (df_turnover['desligamentos'] / 
                                        df_turnover['colaboradores'].replace(0, 1)) * 100

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot)
    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None

# --- 2. BARRA LATERAL ---
st.sidebar.header("📁 Importação")
arquivo_subido = st.sidebar.file_uploader("Selecione o BI_RH.xlsx", type=["xlsx"])

# LEGENDA DOS ÍCONES (Sinalizadores de Tendência)
with st.sidebar.expander("💡 Entenda os Ícones (Deltas)"):
    st.write("As setas comparam o mês atual com o mês anterior:")
    st.write("🔼 **Seta para cima**: O valor aumentou.")
    st.write("🔽 **Seta para baixo**: O valor diminuiu.")
    st.write("🟢 **Verde**: Indica melhora (ex: mais admitidos ou menos turnover).")
    st.write("🔴 **Vermelho**: Indica atenção (ex: mais desligamentos).")

if arquivo_subido:
    dados = carregar_dados(arquivo_subido)
    if dados:
        df_t, df_a, df_af, (c_ini, c_fim, c_mot) = dados

        ano_sel = st.sidebar.selectbox("Ano", sorted(df_t['ano'].unique(), reverse=True))
        df_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel = st.sidebar.selectbox("Mês", df_meses['mes_nome'].unique())

        data_atual = df_meses[df_meses['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        data_ant = data_atual - pd.DateOffset(months=1)
        
        df_atual = df_t[df_t['mês_ano'] == data_atual].iloc[0]
        df_ant_list = df_t[df_t['mês_ano'] == data_ant]
        df_ant = df_ant_list.iloc[0] if not df_ant_list.empty else None

        # --- 3. KPIs ---
        st.title(f"📊 Gestão de RH - {mes_sel}/{ano_sel}")
        def calc_delta(val, col): return (val - df_ant[col]) if df_ant is not None else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Efetivo", int(df_atual['colaboradores']), delta=int(calc_delta(df_atual['colaboradores'], 'colaboradores')))
        c2.metric("Admissões", int(df_atual['admissões']), delta=int(calc_delta(df_atual['admissões'], 'admissões')))
        c3.metric("Desligamentos", int(df_atual['desligamentos']), delta=int(calc_delta(df_atual['desligamentos'], 'desligamentos')), delta_color="inverse")
        c4.metric("Taxa Turnover", f"{df_atual['turnover_taxa']:.2f}%", delta=f"{calc_delta(df_atual['turnover_taxa'], 'turnover_taxa'):.2f}%", delta_color="inverse")

        st.markdown("---")

        # --- 4. GRÁFICO DE TENDÊNCIA COM RETENÇÃO ---
        st.subheader("📈 Evolução Mensal e Taxas de Retenção")
        df_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        
        fig = go.Figure()
        # Barras de Movimentação
        fig.add_trace(go.Bar(x=df_ano['mes_nome'], y=df_ano['admissões'], name='Admissões', 
                             marker_color='#2ecc71', text=df_ano['admissões'], textposition='outside'))
        fig.add_trace(go.Bar(x=df_ano['mes_nome'], y=df_ano['desligamentos'], name='Desligamentos', 
                             marker_color='#e74c3c', text=df_ano['desligamentos'], textposition='outside'))
        
        # Linha de Turnover (Eixo secundário)
        fig.add_trace(go.Scatter(x=df_ano['mes_nome'], y=df_ano['turnover_taxa'], name='Taxa Turnover (%)', 
                                 yaxis='y2', line=dict(color='#f1c40f', width=3), mode='lines+markers+text',
                                 text=df_ano['turnover_taxa'].round(1), textposition='top center'))
        
        # Linha de Retenção (Eixo secundário - conforme solicitado)
        fig.add_trace(go.Scatter(x=df_ano['mes_nome'], y=df_ano['retencao_taxa'], name='Taxa Retenção (%)', 
                                 yaxis='y2', line=dict(color='#9b59b6', width=3, dash='dot'), mode='lines+markers+text',
                                 text=df_ano['retencao_taxa'].round(1), textposition='bottom center'))

        fig.update_layout(
            yaxis=dict(title="Volume de Pessoas"),
            yaxis2=dict(title="Taxas (%)", overlaying='y', side='right', range=[0, max(df_ano['turnover_taxa'].max(), df_ano['retencao_taxa'].max()) + 5]),
            barmode='group',
            legend=dict(orientation="h", y=1.15, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- 5. AFASTAMENTOS ---
        st.markdown("---")
        col_af1, col_af2 = st.columns([1, 2])
        
        fim_mes = data_atual + pd.offsets.MonthEnd(0)
        mask = (df_af[c_ini] <= fim_mes) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_atual))
        df_af_mes = df_af[mask]

        with col_af1:
            st.subheader("📋 Absenteísmo")
            st.metric("Total de Afastados", len(df_af_mes))
            st.info("Soma de todos os colaboradores com afastamento ativo no mês selecionado.")

        with col_af2:
            if not df_af_mes.empty:
                resumo = df_af_mes[c_mot].value_counts().reset_index()
                fig_af = px.bar(resumo, x='count', y=c_mot, orientation='h', text='count', color_discrete_sequence=['#34495e'])
                fig_af.update_traces(textposition='outside')
                st.plotly_chart(fig_af, use_container_width=True)

        with st.expander("Ver lista detalhada"):
            st.dataframe(df_af_mes, use_container_width=True)
else:
    st.info("Importe o arquivo para carregar o Dashboard.")
