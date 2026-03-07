import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH v2", layout="wide")

@st.cache_data
def carregar_dados():
    # Carregamento das abas
    df_turnover = pd.read_excel("BI_RH.xlsx", sheet_name="Turn Over")
    df_admitidos = pd.read_excel("BI_RH.xlsx", sheet_name="Admitidos")

    # --- Tratamento Turnover ---
    # Remove linhas onde a data está vazia para evitar o erro de comparação
    df_turnover = df_turnover.dropna(subset=['Mês_Ano'])
    
    df_turnover['Mês_Ano'] = pd.to_datetime(df_turnover['Mês_Ano'])
    df_turnover['Ano'] = df_turnover['Mês_Ano'].dt.year.astype(int)
    df_turnover['Mes_Nome'] = df_turnover['Mês_Ano'].dt.strftime('%m - %b')
    
    for col in ['Admissões', 'Desligamentos', 'Colaboradores']:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    # Cálculo Turnover Mensal
    df_turnover['Turnover %'] = (((df_turnover['Admissões'] + df_turnover['Desligamentos']) / 2) / df_turnover['Colaboradores']) * 100

    # --- Tratamento Admitidos ---
    df_admitidos['ADMISSAO'] = pd.to_datetime(df_admitidos['ADMISSAO'], errors='coerce')
    df_admitidos['DTDEMISSAO'] = pd.to_datetime(df_admitidos['DTDEMISSAO'], errors='coerce')
    
    # Garante que EMPRESA e SITUACAO sejam sempre texto (evita erro de comparação float/str)
    df_admitidos['EMPRESA'] = df_admitidos['EMPRESA'].astype(str).replace('nan', 'Não Informado')
    
    if 'SITUACAO' not in df_admitidos.columns:
        df_admitidos['SITUACAO'] = 'Ativo'
    else:
        df_admitidos['SITUACAO'] = df_admitidos['SITUACAO'].astype(str).replace('nan', 'Ativo')
        
    return df_turnover, df_admitidos

try:
    df_t, df_a = carregar_dados()
    
    st.title("📊 Gestão de Indicadores RH")

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("Filtros de Visão")
    
    # Filtro por Empresa (Garante que a lista é ordenada corretamente)
    lista_empresas = sorted([x for x in df_a['EMPRESA'].unique() if x != 'Não Informado'])
    empresa_sel = st.sidebar.multiselect("Selecione a Empresa", options=lista_empresas, default=lista_empresas)
    
    # Filtro por Ano
    lista_anos = sorted(df_t['Ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano de Referência", options=lista_anos)

    # Filtro por Mês (Filtrado pelo Ano escolhido)
    df_meses_ano = df_t[df_t['Ano'] == ano_sel]
    lista_meses = sorted(df_meses_ano['Mes_Nome'].unique())
    mes_sel = st.sidebar.selectbox("Mês de Referência", options=lista_meses)

    # --- FILTRAGEM DOS DADOS ---
    df_a_filt = df_a[df_a['EMPRESA'].isin(empresa_sel)]
    df_t_periodo = df_t[(df_t['Ano'] == ano_sel) & (df_t['Mes_Nome'] == mes_sel)]
    df_t_ano = df_t[df_t['Ano'] == ano_sel]

    # --- MÉTRICAS (KPIs) ---
    st.subheader(f"Resultados de {mes_sel}/{ano_sel}")
    c1, c2, c3, c4 = st.columns(4)
    
    if not df_t_periodo.empty:
        linha = df_t_periodo.iloc[0]
        c1.metric("Colaboradores", int(linha['Colaboradores']))
        c2.metric("Admissões", int(linha['Admissões']))
        c3.metric("Desligamentos", int(linha['Desligamentos']))
        c4.metric("Turnover Mensal", f"{linha['Turnover %']:.2f}%")
    else:
        st.warning("Sem dados para o período selecionado.")

    # --- LINHA 2: AFASTAMENTOS E EMPRESA ---
    st.markdown("---")
    col_afast, col_emp = st.columns(2)

    with col_afast:
        st.subheader("🚨 Afastamentos Atuais")
        # Conta afastados ignorando maiúsculas/minúsculas
        qtd_afastados = df_a_filt[df_a_filt['SITUACAO'].str.contains('Afastado', case=False, na=False)].shape[0]
        st.metric("Total de Afastados", qtd_afastados)
        st.caption("Filtro aplicado por Empresa na barra lateral.")

    with col_emp:
        st.subheader("Distribuição por Empresa")
        fig_pie = px.pie(df_a_filt, names='EMPRESA', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- LINHA 3: GRÁFICOS DE TURNOVER ---
    st.markdown("---")
    st.subheader("Evolução do Turnover e Movimentação")
    
    tab1, tab2 = st.tabs(["Visão Mensal (Ano Atual)", "Histórico Completo"])
    
    with tab1:
        # Ordena por mês para o gráfico não ficar bagunçado
        df_t_ano = df_t_ano.sort_values('Mês_Ano')
        fig_mensal = px.bar(df_t_ano, x='Mes_Nome', y='Turnover %', 
                           title=f"Taxa de Turnover Mensal em {ano_sel}",
                           text_auto='.2f')
        fig_mensal.update_traces(marker_color='#ef553b')
        st.plotly_chart(fig_mensal, use_container_width=True)

    with tab2:
        fig_hist = px.line(df_t.sort_values('Mês_Ano'), x='Mês_Ano', y=['Admissões', 'Desligamentos'], 
                          markers=True, title="Histórico de Entradas e Saídas")
        st.plotly_chart(fig_hist, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao processar dados: {e}")
