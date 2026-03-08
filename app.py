import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados():
    # Carregamento das abas
    df_turnover = pd.read_excel("BI_RH.xlsx", sheet_name="Turn Over")
    df_admitidos = pd.read_excel("BI_RH.xlsx", sheet_name="Admitidos")

    # Limpeza preventiva de espaços nos nomes das colunas
    df_turnover.columns = df_turnover.columns.str.strip()
    df_admitidos.columns = df_admitidos.columns.str.strip()

    # --- Tratamento Turnover ---
    df_turnover = df_turnover.dropna(subset=['Mês_Ano'])
    df_turnover['Mês_Ano'] = pd.to_datetime(df_turnover['Mês_Ano'])
    df_turnover['Ano'] = df_turnover['Mês_Ano'].dt.year.astype(int)
    df_turnover['Mes_Nome'] = df_turnover['Mês_Ano'].dt.strftime('%m - %b')
    
    for col in ['Admissões', 'Desligamentos', 'Colaboradores']:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    # Cálculo Turnover Mensal
    df_turnover['Turnover %'] = (((df_turnover['Admissões'] + df_turnover['Desligamentos']) / 2) / df_turnover['Colaboradores']) * 100

    # --- Tratamento Admitidos e Afastamentos ---
    df_admitidos['EMPRESA'] = df_admitidos['EMPRESA'].astype(str).str.strip().replace('nan', 'Não Informado')
    
    # Lógica de Afastado (Coluna corrigida para 'tipo afastamento')
    # Considera afastado se o tipo está preenchido e a data fim está vazia
    df_admitidos['esta_afastado'] = (
        df_admitidos['tipo afastamento'].notnull() & 
        (df_admitidos['tipo afastamento'].astype(str).str.len() > 2) &
        (df_admitidos['data fim'].isnull())
    )
        
    return df_turnover, df_admitidos

try:
    df_t, df_a = carregar_dados()
    
    st.title("📊 Gestão de Indicadores RH")

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("Filtros de Visão")
    
    lista_empresas = sorted([x for x in df_a['EMPRESA'].unique() if x != 'Não Informado'])
    empresa_sel = st.sidebar.multiselect("Selecione a Empresa", options=lista_empresas, default=lista_empresas)
    
    lista_anos = sorted(df_t['Ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano de Referência", options=lista_anos)

    df_meses_ano = df_t[df_t['Ano'] == ano_sel]
    lista_meses = sorted(df_meses_ano['Mes_Nome'].unique())
    mes_sel = st.sidebar
