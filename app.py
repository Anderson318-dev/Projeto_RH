import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Integrado", layout="wide")

@st.cache_data
def carregar_dados():
    try:
        xls = pd.ExcelFile("BI_RH.xlsx")
        lista_abas = xls.sheet_names
        
        # 1. Localização de Abas
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Padronização de Colunas
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_af_raw.columns = df_af_raw.columns.str.strip().str.lower()

        # --- MAPEAMENTO CORRIGIDO (AFASTADOS) ---
        cols_af = df_af_raw.columns
        # Procura "data inicio"
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        # CORREÇÃO: Procura "data termino" ou "fim"
        c_fim = next((c for c in cols_af if 'término' in c or 'término' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)
        c_emp = next((c for c in cols_af if 'empresa' in c or 'unidade' in c), None)

        # Fallbacks de segurança
        if not c_ini: df_af_raw['data_inicio_temp'] = pd.NaT; c_ini = 'data_inicio_temp'
        if not c_fim: df_af_raw['data_término_temp'] = pd.NaT; c_fim = 'data_fim_temp'
        if not c_mot: df_af_raw['motivo_temp'] = "Não Informado"; c_mot = 'motivo_temp'
        if not c_emp: df_af_raw['empresa_temp'] = "Geral"; c_emp = 'empresa_temp'

        # Converter para Data
        df_af_raw[c_ini] = pd.to_datetime(df_af_raw[c_ini], errors='coerce')
        df_af_raw[c_fim] = pd.to_datetime(df_af_raw[c_fim], errors='coerce')

        # --- TRATAMENTO TURNOVER ---
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot, c_emp)

    except Exception as e:
        st.error(f"Erro no Carregamento: {e}")
        st.stop()

# --- INICIALIZAÇÃO ---
df_t, df_a, df_af, cols_map_af = carregar_dados()
c_ini, c_fim, c_mot, c_emp_af = cols_map_af

# --- SIDEBAR: FILTROS ---
st.sidebar.header("Filtros")
col_emp_adm = 'empresa' if 'empresa' in df_a.columns else df_a.columns[0]
lista_empresas = sorted([x for x in df_a[col_emp_adm].unique() if str(x) != 'nan'])
empresa_sel = st.sidebar.multiselect("Empresas", options=lista_empresas, default=lista_empresas)

lista_anos = sorted(df_t['ano'].unique(), reverse=True)
ano_sel = st.sidebar.selectbox("Ano", lista_anos)
df_meses_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
mes_sel = st.sidebar.selectbox("Mês", df_meses_ano['mes_nome'].unique())

# --- CÁLCULOS ---
data_ref = df_meses_ano[df_meses_ano['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
fim_mes_ref = data_ref + pd.offsets.MonthEnd(0)

df_t_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
df_t_periodo = df_t_ano[df_t_ano['mes_nome'] == mes_sel]
df_a_filt = df_a[df_a[col_emp_adm].isin(empresa_sel)]

# Filtragem Afastados (Lógica Temporal)
mask = (df_af[c_ini] <= fim_mes_ref) & (
    (df_af[c_fim].isnull()) | (df_af[c_fim] >= data_ref)
)
df_af_mes = df_af[mask]
if c_emp_af in df_af_mes.columns:
    df_af_mes = df_af_mes[df_af_mes[c_emp_af].isin(empresa_sel)]

# --- DASHBOARD ---
st.title(f"📊 Dashboard RH - {mes_sel}/{ano_sel}")

# KPIs
c1, c2, c3, c4 = st.columns(4)
if not df_t_periodo.empty:
    linha = df_t_periodo.iloc[0]
    c1.metric("Efetivo Total", int(linha['colaboradores']))
    c2.metric("Admissões", int(linha['admissões']))
    c3.metric("Desligamentos", int(linha['desligamentos']))
c4.metric("Afastados no Mês", len(df_af_mes))

st.markdown("---")

# --- GRÁFICO DE EVOLUÇÃO ---
st.subheader("📈 Movimentação Mensal vs Efetivo")
fig_evol = go.Figure()

# Admissões com Rótulo
fig_evol.add_trace(go.Bar(
    x=df_t_ano['mes_nome'], y=df_t_ano['admissões'],
    name='Admissões', marker_color='#2ecc71',
    text=df_t_ano['admissões'].astype(int), textposition='outside'
))

# Desligamentos com Rótulo
fig_evol.add_trace(go.Bar(
    x=df_t_ano['mes_nome'], y=df_t_ano['desligamentos'],
    name='Desligamentos', marker_color='#e74c3c',
    text=df_t_ano['desligamentos'].astype(int), textposition='outside'
))

# Linha de Efetivo
fig_evol.add_trace(go.Scatter(
    x=df_t_ano['mes_nome'], y=df_t_ano['colaboradores'],
    name='Efetivo Total', mode='lines+markers+text',
    text=df_t_ano['colaboradores'].astype(int), textposition="top center",
    line=dict(color='#3498db', width=4), yaxis='y2'
))

fig_evol.update_layout(
    yaxis=dict(title="Movimentação", showgrid=False),
    yaxis2=dict(title="Efetivo Total", overlaying='y', side='right', showgrid=True),
    barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_evol, use_container_width=True)

st.markdown("---")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🥪 Motivos de Afastamento")
    if not df_af_mes.empty:
        resumo_mot = df_af_mes[c_mot].value_counts().reset_index()
        fig_mot = px.bar(resumo_mot, x='count', y=c_mot, orientation='h', color_discrete_sequence=['#FF8C00'])
        st.plotly_chart(fig_mot, use_container_width=True)
    else:
        st.info("Sem afastamentos neste período.")

with col_right:
    st.subheader("🏢 Colaboradores por Empresa")
    fig_pie = px.pie(df_a_filt, names=col_emp_adm, hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

with st.expander("📋 Ver Lista Detalhada de Afastados"):
    st.dataframe(df_af_mes)
