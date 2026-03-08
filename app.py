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

    # --- LIMPEZA RADICAL DE COLUNAS ---
    # Transforma tudo em minúsculo e tira espaços (Ex: "Tipo Afastamento " vira "tipo afastamento")
    df_turnover.columns = df_turnover.columns.str.strip().str.lower()
    df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()

    # --- Tratamento Turnover ---
    # Nota: Agora as colunas devem ser chamadas em minúsculo no código
    df_turnover = df_turnover.dropna(subset=['mês_ano'])
    df_turnover['mês_ano'] = pd.to_datetime(df_turnover['mês_ano'])
    df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
    df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
    
    for col in ['admissões', 'desligamentos', 'colaboradores']:
        df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

    # Cálculo Turnover Mensal
    df_turnover['turnover %'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / df_turnover['colaboradores']) * 100

    # --- Tratamento Admitidos e Afastamentos ---
    df_admitidos['empresa'] = df_admitidos['empresa'].astype(str).str.strip().replace('nan', 'Não Informado')
    
    # Lógica de Afastado (Usando nomes limpos em minúsculo)
    # Verifica se a coluna existe antes de processar
    if 'tipo afastamento' in df_admitidos.columns:
        df_admitidos['esta_afastado'] = (
            df_admitidos['tipo afastamento'].notnull() & 
            (df_admitidos['tipo afastamento'].astype(str).str.len() > 2) &
            (df_admitidos['data fim'].isnull())
        )
    else:
        df_admitidos['esta_afastado'] = False
        st.error(f"Coluna 'tipo afastamento' não encontrada. Colunas lidas: {list(df_admitidos.columns)}")
        
    return df_turnover, df_admitidos

try:
    df_t, df_a = carregar_dados()
    
    st.title("📊 Gestão de Indicadores RH")

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("Filtros de Visão")
    
    lista_empresas = sorted([x for x in df_a['empresa'].unique() if x != 'Não Informado'])
    empresa_sel = st.sidebar.multiselect("Selecione a Empresa", options=lista_empresas, default=lista_empresas)
    
    lista_anos = sorted(df_t['ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano de Referência", options=lista_anos)

    df_meses_ano = df_t[df_t['ano'] == ano_sel]
    lista_meses = sorted(df_meses_ano['mes_nome'].unique())
    mes_sel = st.sidebar.selectbox("Mês de Referência", options=lista_meses)

    # --- FILTRAGEM DOS DADOS ---
    df_a_filt = df_a[df_a['empresa'].isin(empresa_sel)]
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
        df_afastados_lista = df_a_filt[df_a_filt['esta_afastado'] == True]
        qtd_afastados = df_afastados_lista.shape[0]
        st.metric("Total Afastados (Ativos s/ Retorno)", qtd_afastados)
        
        if qtd_afastados > 0:
            with st.expander("Ver detalhes dos afastados"):
                # Ajustado para minúsculo
                st.dataframe(df_afastados_lista[['nome', 'tipo afastamento', 'empresa']])
        else:
            st.info("Nenhum colaborador afastado detectado (Data Fim vazia).")

    with col_emp:
        st.subheader("Colaboradores por Empresa")
        fig_pie = px.pie(df_a_filt, names='empresa', hole=0.4)
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
