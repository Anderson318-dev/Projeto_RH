import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados():
    # Carregamento das 3 abas
    df_turnover = pd.read_excel("BI_RH.xlsx", sheet_name="Turn Over")
    df_admitidos = pd.read_excel("BI_RH.xlsx", sheet_name="Admitidos")
    
    try:
        df_afastados_base = pd.read_excel("BI_RH.xlsx", sheet_name="afastado")
    except:
        # Caso a aba mude de nome acidentalmente para "Afastado" ou "Afastados"
        df_afastados_base = pd.read_excel("BI_RH.xlsx", sheet_name=0) # Pega a primeira aba como fallback

    # --- LIMPEZA RADICAL DE COLUNAS ---
    df_turnover.columns = df_turnover.columns.str.strip().str.lower()
    df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
    df_afastados_base.columns = df_afastados_base.columns.str.strip().str.lower()

    # --- Tratamento Turnover ---
    df_turnover = df_turnover.dropna(subset=['mês_ano'])
    df_turnover['mês_ano'] = pd.to_datetime(df_turnover['mês_ano'])
    df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
    df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
    
    for col in ['admissões', 'desligamentos', 'colaboradores']:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    df_turnover['turnover %'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / df_turnover['colaboradores']) * 100

    # --- Tratamento Afastamentos (Aba "afastado") ---
    # Lógica: Se 'data fim' está vazio, a pessoa continua afastada
    if 'data fim' in df_afastados_base.columns:
        df_afastados_base['esta_afastado'] = df_afastados_base['data fim'].isnull()
    else:
        # Se não achar a coluna 'data fim', considera todos da lista como afastados atuais
        df_afastados_base['esta_afastado'] = True

    return df_turnover, df_admitidos, df_afastados_base

try:
    df_t, df_a, df_af = carregar_dados()
    
    st.title("📊 Gestão de Indicadores RH")

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("Filtros de Visão")
    
    # Filtro por Empresa (usando a base de admitidos)
    lista_empresas = sorted([x for x in df_a['empresa'].unique() if str(x) != 'nan'])
    empresa_sel = st.sidebar.multiselect("Selecione a Empresa", options=lista_empresas, default=lista_empresas)
    
    # Filtro por Ano
    lista_anos = sorted(df_t['ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano de Referência", options=lista_anos)

    # Filtro por Mês
    df_meses_ano = df_t[df_t['ano'] == ano_sel]
    lista_meses = sorted(df_meses_ano['mes_nome'].unique())
    mes_sel = st.sidebar.selectbox("Mês de Referência", options=lista_meses)

    # --- FILTRAGEM DOS DADOS ---
    df_a_filt = df_a[df_a['empresa'].isin(empresa_sel)]
    df_af_filt = df_af[df_af['empresa'].isin(empresa_sel)]
    df_t_periodo = df_t[(df_t['ano'] == ano_sel) & (df_t['mes_nome'] == mes_sel)]
    df_t_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')

    # --- MÉTRICAS (KPIs) ---
    st.subheader(f"📍 Indicadores: {mes_sel}/{ano_sel}")
    c1, c2, c3, c4 = st.columns(4)
    
    if not df_t_periodo.empty:
        linha = df_t_periodo.iloc[0]
        c1.metric("Colaboradores Ativos", int(linha['colaboradores']))
        c2.metric("Admissões no Mês", int(linha['admissões']))
        c3.metric("Desligamentos no Mês", int(linha['desligamentos']))
        c4.metric("Taxa de Turnover", f"{linha['turnover %']:.2f}%")

    st.markdown("---")

    # --- LINHA 2: AFASTAMENTOS E PIZZA ---
    col_afast, col_emp = st.columns(2)

    with col_afast:
        st.subheader("🚨 Afastamentos Atuais")
        # Filtra apenas quem está marcado como afastado (data fim vazia)
        df_ativos_afastados = df_af_filt[df_af_filt['esta_afastado'] == True]
        qtd_afastados = df_ativos_afastados.shape[0]
        st.metric("Total Afastados (Sem data retorno)", qtd_afastados)
        
        if qtd_afastados > 0:
            with st.expander("Ver detalhes dos afastados"):
                # Ajustando para os nomes de colunas que podem estar na aba afastado
                colunas_mostrar = [c for c in ['nome funcionario', 'nome', 'tipo afastamento', 'empresa'] if c in df_ativos_afastados.columns]
                st.dataframe(df_ativos_afastados[colunas_mostrar])
        else:
            st.info("Nenhum colaborador com afastamento em aberto encontrado.")

    with col_emp:
        st.subheader("Distribuição por Empresa (Ativos)")
        fig_pie = px.pie(df_a_filt, names='empresa', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- LINHA 3: GRÁFICO DE EVOLUÇÃO ---
    st.markdown("---")
    st.subheader("📈 Evolução Mensal: Movimentação vs Efetivo")

    fig_evolucao = go.Figure()
    fig_evolucao.add_trace(go.Bar(x=df_t_ano['mes_nome'], y=df_t_ano['admissões'], name='Admissões', marker_color='#2ecc71'))
    fig_evolucao.add_trace(go.Bar(x=df_t_ano['mes_nome'], y=df_t_ano['desligamentos'], name='Desligamentos', marker_color='#e74c3c'))
    fig_evolucao.add_trace(go.Scatter(x=df_t_ano['mes_nome'], y=df_t_ano['colaboradores'], name='Efetivo Total', 
                                     mode='lines+markers+text', text=df_t_ano['colaboradores'].astype(int), 
                                     textposition="top center", line=dict(color='#3498db', width=4), yaxis='y2'))

    fig_evolucao.update_layout(yaxis=dict(title="Movimentação"), yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), barmode='group')

    st.plotly_chart(fig_evolucao, use_container_width=True)

except Exception as e:
    st.error(f"Erro detectado: {e}")
