import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados():
    try:
        # Carrega o arquivo Excel completo
        xls = pd.ExcelFile("BI_RH.xlsx")
        lista_abas = xls.sheet_names
        
        # --- Busca Inteligente de Abas ---
        # Procura abas que contenham nomes similares
        aba_turnover = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_admitidos = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_afastado = next((s for s in lista_abas if 'afast' in s.lower()), None)

        if not aba_turnover or not aba_admitidos:
            st.error(f"Abas principais não encontradas! Abas no arquivo: {lista_abas}")
            st.stop()

        df_turnover = pd.read_excel(xls, sheet_name=aba_turnover)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_admitidos)
        
        # Se não achar aba de afastado, cria um dataframe vazio para não quebrar
        if aba_afastado:
            df_afastados_base = pd.read_excel(xls, sheet_name=aba_afastado)
        else:
            df_afastados_base = pd.DataFrame(columns=['empresa', 'nome', 'tipo afastamento', 'data fim'])

        # --- LIMPEZA DE COLUNAS ---
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_afastados_base.columns = df_afastados_base.columns.str.strip().str.lower()

        # --- Tratamento Turnover ---
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        for col in ['admissões', 'desligamentos', 'colaboradores']:
            if col in df_turnover.columns:
                df_turnover[col] = pd.to_numeric(df_turnover[col], errors='coerce').fillna(0)

        df_turnover['turnover %'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / df_turnover['colaboradores']) * 100

        # --- Lógica de Afastados ---
        if 'data fim' in df_afastados_base.columns:
            # Considera afastado se 'data fim' for nulo
            df_afastados_base['esta_afastado'] = df_afastados_base['data fim'].isnull()
        else:
            df_afastados_base['esta_afastado'] = False

        return df_turnover, df_admitidos, df_afastados_base

    except Exception as e:
        st.error(f"Erro ao processar o arquivo Excel: {e}")
        st.stop()

try:
    df_t, df_a, df_af = carregar_dados()
    
    st.title("📊 Gestão de Indicadores RH")

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("Filtros de Visão")
    
    # Filtro de Empresa
    col_emp = 'empresa' if 'empresa' in df_a.columns else df_a.columns[0]
    lista_empresas = sorted([x for x in df_a[col_emp].unique() if str(x) != 'nan'])
    empresa_sel = st.sidebar.multiselect("Selecione a Empresa", options=lista_empresas, default=lista_empresas)
    
    # Filtro de Ano e Mês
    lista_anos = sorted(df_t['ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano de Referência", options=lista_anos)
    df_meses_ano = df_t[df_t['ano'] == ano_sel]
    lista_meses = sorted(df_meses_ano['mes_nome'].unique())
    mes_sel = st.sidebar.selectbox("Mês de Referência", options=lista_meses)

    # --- FILTRAGEM ---
    df_a_filt = df_a[df_a[col_emp].isin(empresa_sel)]
    
    # Filtro de afastados
    col_emp_af = 'empresa' if 'empresa' in df_af.columns else None
    df_af_filt = df_af[df_af[col_emp_af].isin(empresa_sel)] if col_emp_af else df_af

    df_t_periodo = df_t[(df_t['ano'] == ano_sel) & (df_t['mes_nome'] == mes_sel)]
    df_t_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')

    # --- KPIs ---
    st.subheader(f"📍 Indicadores: {mes_sel}/{ano_sel}")
    c1, c2, c3, c4 = st.columns(4)
    
    if not df_t_periodo.empty:
        linha = df_t_periodo.iloc[0]
        c1.metric("Colaboradores Ativos", int(linha['colaboradores']))
        c2.metric("Admissões no Mês", int(linha['admissões']))
        c3.metric("Desligamentos no Mês", int(linha['desligamentos']))
        c4.metric("Taxa de Turnover", f"{linha['turnover %']:.2f}%")

    st.markdown("---")

    # --- AFASTAMENTOS E PIZZA ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🚨 Afastamentos Atuais")
        df_ativos_afastados = df_af_filt[df_af_filt['esta_afastado'] == True]
        qtd_afastados = df_ativos_afastados.shape[0]
        st.metric("Total Afastados (Ativos s/ Retorno)", qtd_afastados)
        
        if qtd_afastados > 0:
            with st.expander("Ver detalhes dos afastados"):
                cols_view = [c for c in ['nome funcionario', 'nome', 'tipo afastamento', 'empresa'] if c in df_af_filt.columns]
                st.dataframe(df_ativos_afastados[cols_view])
        elif 'esta_afastado' not in df_af.columns or df_af.empty:
            st.warning("Aba de afastamento não encontrada ou sem dados.")

    with col2:
        st.subheader("Distribuição por Empresa (Ativos)")
        fig_pie = px.pie(df_a_filt, names=col_emp, hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- GRÁFICO DE EVOLUÇÃO ---
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
    st.error(f"Erro: {e}")
