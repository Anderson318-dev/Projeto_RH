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

    # --- Tratamento Turnover ---
    df_turnover = df_turnover.dropna(subset=['Mês_Ano'])
    df_turnover['Mês_Ano'] = pd.to_datetime(df_turnover['Mês_Ano'])
    df_turnover['Ano'] = df_turnover['Mês_Ano'].dt.year.astype(int)
    df_turnover['Mes_Nome'] = df_turnover['Mês_Ano'].dt.strftime('%m - %b')
    
    for col in ['Admissões', 'Desligamentos', 'Colaboradores']:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    df_turnover['Turnover %'] = (((df_turnover['Admissões'] + df_turnover['Desligamentos']) / 2) / df_turnover['Colaboradores']) * 100

    # --- Tratamento Admitidos e Afastamentos ---
    df_admitidos['EMPRESA'] = df_admitidos['EMPRESA'].astype(str).str.strip().replace('nan', 'Não Informado')
    
    # Lógica de Afastado: 
    # 1. 'tipo de afastamento' NÃO está vazio
    # 2. 'data fim' ESTÁ vazio (isnull)
    df_admitidos['esta_afastado'] = (
        df_admitidos['tipo de afastamento'].notnull() & 
        (df_admitidos['tipo de afastamento'].astype(str).str.len() > 2) &
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
    mes_sel = st.sidebar.selectbox("Mês de Referência", options=lista_meses)

    # --- FILTRAGEM DOS DADOS ---
    df_a_filt = df_a[df_a['EMPRESA'].isin(empresa_sel)]
    df_t_periodo = df_t[(df_t['Ano'] == ano_sel) & (df_t['Mes_Nome'] == mes_sel)]
    df_t_ano = df_t[df_t['Ano'] == ano_sel].sort_values('Mês_Ano')

    # --- MÉTRICAS (KPIs) ---
    st.subheader(f"📍 Indicadores: {mes_sel}/{ano_sel}")
    c1, c2, c3, c4 = st.columns(4)
    
    if not df_t_periodo.empty:
        linha = df_t_periodo.iloc[0]
        c1.metric("Colaboradores Ativos", int(linha['Colaboradores']))
        c2.metric("Admissões no Mês", int(linha['Admissões']))
        c3.metric("Desligamentos no Mês", int(linha['Desligamentos']))
        c4.metric("Taxa de Turnover", f"{linha['Turnover %']:.2f}%")

    st.markdown("---")

    # --- LINHA 2: AFASTAMENTOS E PIZZA ---
    col_afast, col_emp = st.columns(2)

    with col_afast:
        st.subheader("🚨 Afastamentos Atuais")
        df_afastados_lista = df_a_filt[df_a_filt['esta_afastado'] == True]
        qtd_afastados = df_afastados_lista.shape[0]
        
        st.metric("Total Afastados (Ativos s/ Retorno)", qtd_afastados)
        
        if qtd_afastados > 0:
            with st.expander("Ver detalhes dos afastados"):
                st.dataframe(df_afastados_lista[['NOME', 'tipo de afastamento', 'data inicio', 'EMPRESA']])
        else:
            st.info("Nenhum colaborador com campo 'data fim' vazio e tipo preenchido.")

    with col_emp:
        st.subheader("Colaboradores por Empresa")
        fig_pie = px.pie(df_a_filt, names='EMPRESA', hole=0.4, color_discrete_sequence=px.colors.qualitative.Prism)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- LINHA 3: GRÁFICO DE EVOLUÇÃO (BARRAS + LINHA) ---
    st.markdown("---")
    st.subheader("📈 Evolução Mensal: Movimentação vs Efetivo")

    fig_evolucao = go.Figure()

    # Admissões (Barras Verdes)
    fig_evolucao.add_trace(go.Bar(
        x=df_t_ano['Mes_Nome'], y=df_t_ano['Admissões'],
        name='Admissões', marker_color='#2ecc71', offsetgroup=1
    ))

    # Desligamentos (Barras Vermelhas)
    fig_evolucao.add_trace(go.Bar(
        x=df_t_ano['Mes_Nome'], y=df_t_ano['Desligamentos'],
        name='Desligamentos', marker_color='#e74c3c', offsetgroup=1
    ))

    # Efetivo Total (Linha Azul no Eixo Secundário)
    fig_evolucao.add_trace(go.Scatter(
        x=df_t_ano['Mes_Nome'], y=df_t_ano['Colaboradores'],
        name='Efetivo Total', mode='lines+markers+text',
        text=df_t_ano['Colaboradores'].astype(int), textposition="top center",
        line=dict(color='#3498db', width=4), yaxis='y2'
    ))

    fig_evolucao.update_layout(
        xaxis=dict(title="Meses"),
        yaxis=dict(title="Movimentação (Adm/Desl)", showgrid=False),
        yaxis2=dict(title="Efetivo Total", overlaying='y', side='right', showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        barmode='group',
        height=550
    )

    st.plotly_chart(fig_evolucao, use_container_width=True)

except Exception as e:
    st.error(f"Erro detectado: {e}")
