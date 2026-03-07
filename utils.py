import pandas as pd
import streamlit as st
from datetime import datetime

@st.cache_data
def carregar_dados():
    # Carregamento das planilhas
    df_turnover = pd.read_excel("BI_RH.xlsx", sheet_name="Turn Over")
    df_admitidos = pd.read_excel("BI_RH.xlsx", sheet_name="Admitidos")

    # --- Tratamento df_turnover ---
    # Conversão de data e criação de Ano-Mês
    df_turnover['Mês_Ano'] = pd.to_datetime(df_turnover['Mês_Ano'])
    df_turnover['Ano-Mês'] = df_turnover['Mês_Ano'].dt.strftime('%Y-%m')

    # Conversão numérica (tratando fórmulas do Excel)
    cols_numericas = ['Admissões', 'Desligamentos', 'Colaboradores']
    for col in cols_numericas:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    # Recálculo de Métricas
    # Turnover = ((Admissões + Desligamentos) / 2) / Colaboradores
    df_turnover['Turnover'] = ((df_turnover['Admissões'] + df_turnover['Desligamentos']) / 2) / df_turnover['Colaboradores']
    # Taxa de Retenção (Exemplo solicitado: Desligamentos / Colaboradores - geralmente é 1 - turnover, mas seguindo sua fórmula)
    df_turnover['Taxa de Retenção'] = df_turnover['Desligamentos'] / df_turnover['Colaboradores']

    # --- Tratamento df_admitidos ---
    df_admitidos['ADMISSAO'] = pd.to_datetime(df_admitidos['ADMISSAO'])
    df_admitidos['DTDEMISSAO'] = pd.to_datetime(df_admitidos['DTDEMISSAO'], errors='coerce')

    # Cálculo de Tempo de Casa (Data de referência: 31/12/2025)
    data_ref = pd.to_datetime("2025-12-31")
    
    def calcular_tempo(row):
        fim = row['DTDEMISSAO'] if pd.notnull(row['DTDEMISSAO']) else data_ref
        diff = (fim - row['ADMISSAO']).days
        return round(diff / 365.25, 2) # Retorna em anos

    df_admitidos['Tempo de Casa (Anos)'] = df_admitidos.apply(calcular_tempo, axis=1)
    
    # Status Ativo/Inativo
    df_admitidos['Status'] = df_admitidos['DTDEMISSAO'].apply(lambda x: 'Ativo' if pd.isnull(x) else 'Desligado')

    return df_turnover, df_admitidos