import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados():
    try:
        xls = pd.ExcelFile("BI_RH.xlsx")
        lista_abas = xls.sheet_names
        
        # Busca inteligente de abas
        aba_turnover = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_admitidos = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_afastado = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_turnover)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_admitidos)
        df_afastados_base = pd.read_excel(xls, sheet_name=aba_afastado)

        # Padronização de colunas (minúsculo e sem espaços)
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_afastados_base.columns = df_afastados_base.columns.str.strip().str.lower()

        # Tratamento de Datas na aba Afastados
        df_afastados_base['data inicio'] = pd.to_datetime(df_afastados_base['data inicio'], errors='coerce')
        df_afastados_base['data fim'] = pd.to_datetime(df_afastados_base['data fim'], errors='coerce')
        
        # Tratamento Turnover
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover['mês_ano'], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')

        return df_turnover, df_admitidos, df_afastados_base
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

df_t, df_a, df_af = carregar_dados()

# --- SIDEBAR: FILTROS ---
st.sidebar.header("Filtros Globais")

# Filtro Empresa
col_emp = 'empresa' if 'empresa' in df_a.columns else df_a.columns[0]
lista_empresas = sorted(df_a[col_emp].unique().astype(str))
empresa_sel = st.sidebar.multiselect("Selecione a Empresa", options=lista_empresas, default=lista_empresas)

# Filtro Ano
lista_anos = sorted(df_t['ano'].unique(), reverse=True)
ano_sel = st.sidebar.selectbox("Ano de Referência", options=lista_anos)

# Filtro Mês
df_meses_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
lista_meses = df_meses_ano['mes_nome'].unique()
mes_sel = st.sidebar.selectbox("Mês de Referência", options=lista_meses)

# --- PROCESSAMENTO DOS FILTROS ---
data_referencia = df_meses_ano[df_meses_ano['mes_nome'] == mes_sel]['mês_ano'].iloc[0]

# Filtrar Afastados Ativos no Mês Selecionado
# Regra: data inicio <= fim do mês selecionado E (data fim >= inicio do mês OU data fim é vazia)
def filtrar_afastados_no_mes(df, data_ref, empresas):
    df_f = df[df[col_emp].isin(empresas)].copy()
    
    # Define o último dia do mês de referência para a comparação
    fim_mes_ref = data_ref + pd.offsets.MonthEnd(0)
    
    mask = (df_f['data inicio'] <= fim_mes_ref) & (
        (df_f['data fim'].isnull()) | (df_f['data fim'] >= data_ref)
    )
    return df_f[mask]

df_af_mes = filtrar_afastados_no_mes(df_af, data_referencia, empresa_sel)
df_t_periodo = df_t[(df_t['ano'] == ano_sel) & (df_t['mes_nome'] == mes_sel)]

# --- DASHBOARD ---
st.title(f"📊 Consolidado de Afastamentos - {mes_sel}/{ano_sel}")

# KPIs Superiores
c1, c2, c3 = st.columns(3)
total_afastados = len(df_af_mes)
c1.metric("Total Afastados no Mês", total_afastados)

# Evolução de Afastados no Ano (Calculado dinamicamente para cada mês do ano)
historico_afastados = []
for _, row in df_meses_ano.iterrows():
    qtd = len(filtrar_afastados_no_mes(df_af, row['mês_ano'], empresa_sel))
    historico_afastados.append(qtd)
df_meses_ano['qtd_afastados'] = historico_afastados

st.markdown("---")

col_esq, col_dir = st.columns(2)

with col_esq:
    st.subheader("🥪 Motivos de Afastamento")
    if not df_af_mes.empty and 'tipo afastamento' in df_af_mes.columns:
        fig_motivo = px.bar(
            df_af_mes['tipo afastamento'].value_counts().reset_index(),
            x='count', y='tipo afastamento', orientation='h',
            labels={'count': 'Qtd Colaboradores', 'tipo afastamento': 'Motivo'},
            color_discrete_sequence=['#FF8C00']
        )
        st.plotly_chart(fig_motivo, use_container_width=True)
    else:
        st.info("Sem dados de motivos para este período.")

with col_dir:
    st.subheader("🏢 Afastados por Empresa")
    if not df_af_mes.empty:
        fig_emp = px.pie(
            df_af_mes, names=col_emp, hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_emp, use_container_width=True)

st.markdown("---")

# Gráfico de Evolução Anual de Afastamentos
st.subheader("📈 Evolução Mensal de Afastamentos (Ano Selecionado)")
fig_evol_afast = px.line(
    df_meses_ano, x='mes_nome', y='qtd_afastados',
    markers=True, text='qtd_afastados',
    labels={'qtd_afastados': 'Qtd Afastados', 'mes_nome': 'Mês'},
    line_shape='spline'
)
fig_evol_afast.update_traces(textposition="top center", line_color="#E74C3C")
st.plotly_chart(fig_evol_afast, use_container_width=True)

# Listagem Detalhada
st.markdown("---")
with st.expander("📋 Ver Lista Detalhada de Afastados do Período"):
    if not df_af_mes.empty:
        # Tenta identificar o nome do funcionário
        col_nome = next((c for c in df_af_mes.columns if 'nome' in c), df_af_mes.columns[0])
        st.dataframe(df_af_mes[[col_nome, col_emp, 'tipo afastamento', 'data inicio', 'data fim']].sort_values('data inicio'))
    else:
        st.write("Nenhum registro encontrado.")
