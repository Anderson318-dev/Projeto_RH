import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard de RH", layout="wide")

# --- FUNÇÃO DE CARREGAMENTO (Embutida) ---
@st.cache_data
def carregar_dados():
    # Tenta carregar o arquivo
    df_turnover = pd.read_excel("BI_RH.xlsx", sheet_name="Turn Over")
    df_admitidos = pd.read_excel("BI_RH.xlsx", sheet_name="Admitidos")

    # Tratamento Turnover
    df_turnover['Mês_Ano'] = pd.to_datetime(df_turnover['Mês_Ano'])
    df_turnover['Ano-Mês'] = df_turnover['Mês_Ano'].dt.strftime('%Y-%m')
    
    for col in ['Admissões', 'Desligamentos', 'Colaboradores']:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    df_turnover['Turnover'] = ((df_turnover['Admissões'] + df_turnover['Desligamentos']) / 2) / df_turnover['Colaboradores']

    # Tratamento Admitidos
    df_admitidos['ADMISSAO'] = pd.to_datetime(df_admitidos['ADMISSAO'])
    df_admitidos['DTDEMISSAO'] = pd.to_datetime(df_admitidos['DTDEMISSAO'], errors='coerce')
    
    data_ref = pd.to_datetime("2025-12-31")
    df_admitidos['Tempo de Casa (Anos)'] = df_admitidos.apply(
        lambda r: round(((r['DTDEMISSAO'] if pd.notnull(r['DTDEMISSAO']) else data_ref) - r['ADMISSAO']).days / 365.25, 2), axis=1
    )
    df_admitidos['Status'] = df_admitidos['DTDEMISSAO'].apply(lambda x: 'Ativo' if pd.isnull(x) else 'Desligado')

    return df_turnover, df_admitidos

# --- EXECUÇÃO ---
try:
    df_t, df_a = carregar_dados()
    
    st.title("📊 Dashboard de RH Profissional")

    # Sidebar
    st.sidebar.header("Filtros")
    empresas = st.sidebar.multiselect("Empresa", options=df_a['EMPRESA'].unique(), default=df_a['EMPRESA'].unique())
    df_a_filt = df_a[df_a['EMPRESA'].isin(empresas)]

    # KPIs
    ultimo = df_t.iloc[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("Ativos Total", int(ultimo['Colaboradores']))
    c2.metric("Admissões (Mês)", int(ultimo['Admissões']))
    c3.metric("Turnover", f"{ultimo['Turnover']*100:.2f}%")

    # Gráficos
    col_esq, col_dir = st.columns(2)
    with col_esq:
        fig1 = px.line(df_t, x='Ano-Mês', y=['Admissões', 'Desligamentos'], title="Movimentação")
        st.plotly_chart(fig1, use_container_width=True)
    
    with col_dir:
        fig2 = px.pie(df_a_filt, names='EMPRESA', title="Distribuição por Empresa")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Base de Dados")
    st.dataframe(df_a_filt.head(50))

except Exception as e:
    st.error(f"Erro ao carregar os dados: {e}")
    st.info("Verifique se o arquivo BI_RH.xlsx está na raiz do GitHub e se as abas se chamam 'Turn Over' e 'Admitidos'.")
