import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
# Define o título da aba do navegador e o layout expandido (wide)
st.set_page_config(page_title="Dashboard RH Integrado", layout="wide")

@st.cache_data  # Mantém os dados em memória para não ler o Excel a cada clique
def carregar_dados():
    try:
        # Abre o arquivo Excel principal
        xls = pd.ExcelFile("BI_RH.xlsx")
        lista_abas = xls.sheet_names
        
        # Identifica as abas ignorando letras maiúsculas/minúsculas
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        # Transforma as abas em DataFrames (tabelas do Python)
        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Limpa nomes das colunas (remove espaços e coloca em minúsculo)
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_af_raw.columns = df_af_raw.columns.str.strip().str.lower()

        # --- MAPEAMENTO DE COLUNAS DE AFASTAMENTO ---
        # Tenta encontrar colunas de data e motivo mesmo que o nome mude levemente
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)
        c_emp = next((c for c in cols_af if 'empresa' in c or 'unidade' in c), None)

        # Se não encontrar as colunas, cria valores padrão para o código não travar
        if not c_ini: df_af_raw['data_inicio_temp'] = pd.NaT; c_ini = 'data_inicio_temp'
        if not c_fim: df_af_raw['data_término_temp'] = pd.NaT; c_fim = 'data_fim_temp'
        if not c_mot: df_af_raw['motivo_temp'] = "Não Informado"; c_mot = 'motivo_temp'
        if not c_emp: df_af_raw['empresa_temp'] = "Geral"; c_emp = 'empresa_temp'

        # Garante que as colunas de data sejam reconhecidas como DATAS pelo Python
        df_af_raw[c_ini] = pd.to_datetime(df_af_raw[c_ini], errors='coerce')
        df_af_raw[c_fim] = pd.to_datetime(df_af_raw[c_fim], errors='coerce')

        # --- TRATAMENTO DA ABA TURNOVER ---
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano']) # Remove linhas sem data
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b') # Cria nome: "01 - Jan"
        
        # Garante que números sejam lidos como números (evita erro de texto no Excel)
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot, c_emp)

    except Exception as e:
        st.error(f"Erro Crítico: Verifique o arquivo Excel. Detalhes: {e}")
        st.stop()

# --- 2. EXECUÇÃO INICIAL ---
df_t, df_a, df_af, cols_map_af = carregar_dados()
c_ini, c_fim, c_mot, c_emp_af = cols_map_af

# --- 3. BARRA LATERAL (FILTROS) ---
st.sidebar.header("Filtros do Dashboard")

# Filtro de Empresa (Baseado na aba de Admitidos/Efetivo)
col_emp_adm = 'empresa' if 'empresa' in df_a.columns else df_a.columns[0]
lista_empresas = sorted([x for x in df_a[col_emp_adm].unique() if str(x) != 'nan'])
empresa_sel = st.sidebar.multiselect("Selecione as Empresas", options=lista_empresas, default=lista_empresas)

# Filtro de Ano e Mês (Baseado na aba de Turnover)
lista_anos = sorted(df_t['ano'].unique(), reverse=True)
ano_sel = st.sidebar.selectbox("Selecione o Ano", lista_anos)
df_meses_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
mes_sel = st.sidebar.selectbox("Selecione o Mês", df_meses_ano['mes_nome'].unique())

# --- 4. CÁLCULOS DE APOIO ---
# Identifica a data exata de referência para filtrar os afastados corretamente
data_ref = df_meses_ano[df_meses_ano['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
fim_mes_ref = data_ref + pd.offsets.MonthEnd(0)

# Filtra o DataFrame de evolução anual para o gráfico
df_t_ano = df_t[df_t['ano'] == ano_sel].copy().sort_values('mês_ano')

# CALCULA A TAXA DE TURNOVER: ((Admissões + Desligamentos) / 2) / Efetivo
df_t_ano['turnover_taxa'] = (
    ((df_t_ano['admissões'] + df_t_ano['desligamentos']) / 2) / 
    df_t_ano['colaboradores'].replace(0, 1) # Proteção contra divisão por zero
) * 100

# Seleciona apenas a linha do mês escolhido para os KPIs
df_t_periodo = df_t_ano[df_t_ano['mes_nome'] == mes_sel]
df_a_filt = df_a[df_a[col_emp_adm].isin(empresa_sel)]

# Lógica de Afastados: Início <= Fim do Mês E (Término vazio OU Término >= Início do Mês)
mask_mes = (df_af[c_ini] <= fim_mes_ref) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_ref))
df_af_mes = df_af[mask_mes]
if c_emp_af in df_af_mes.columns:
    df_af_mes = df_af_mes[df_af_mes[c_emp_af].isin(empresa_sel)]

# --- 5. INTERFACE DO DASHBOARD ---
st.title(f"📊 Dashboard RH - {mes_sel}/{ano_sel}")

# Bloco de KPIs (Cards superiores)
c1, c2, c3, c4 = st.columns(4)
if not df_t_periodo.empty:
    linha = df_t_periodo.iloc[0]
    c1.metric("Efetivo Total", int(linha['colaboradores']))
    c2.metric("Admissões", int(linha['admissões']))
    c3.metric("Desligamentos", int(linha['desligamentos']))
    c4.metric("Taxa Turnover", f"{linha['turnover_taxa']:.2f}%")

st.markdown("---")

# --- 6. GRÁFICO DE EVOLUÇÃO ---
st.subheader("📈 Movimentação Mensal vs Total Efetivos")
fig_evol = go.Figure()

# Barras de Admissões (Verde)
fig_evol.add_trace(go.Bar(
    x=df_t_ano['mes_nome'], y=df_t_ano['admissões'],
    name='Admissões', marker_color='#2ecc71',
    text=df_t_ano['admissões'].astype(int), textposition='outside'
))

# Barras de Desligamentos (Vermelho)
fig_evol.add_trace(go.Bar(
    x=df_t_ano['mes_nome'], y=df_t_ano['desligamentos'],
    name='Desligamentos', marker_color='#e74c3c',
    text=df_t_ano['desligamentos'].astype(int), textposition='outside'
))

# Linha de Efetivo (Azul) - Usa o eixo da direita (yaxis='y2')
fig_evol.add_trace(go.Scatter(
    x=df_t_ano['mes_nome'], y=df_t_ano['colaboradores'],
    name='Efetivo Total', mode='lines+markers+text',
    text=df_t_ano['colaboradores'].astype(int), textposition="top center",
    line=dict(color='#3498db', width=4), 
    yaxis='y2'
))

# Ajustes de Layout e Eixos
fig_evol.update_layout(
    yaxis=dict(title="Qtd Movimentação", showgrid=False),
    yaxis2=dict(title="Total Efetivos", overlaying='y', side='right', showgrid=True),
    barmode='group', 
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_evol, use_container_width=True)

st.markdown("---")

# --- 7. BLOCOS INFERIORES (AFASTADOS E PIZZA) ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🥪 Motivos de Afastamento")
    # Mostra a quantidade total como um alerta informativo
    st.info(f"**Total de Afastados no período:** {len(df_af_mes)}")
    
    if not df_af_mes.empty:
        # Conta quantos afastados por cada motivo
        resumo_mot = df_af_mes[c_mot].value_counts().reset_index()
        fig_mot = px.bar(resumo_mot, x='count', y=c_mot, orientation='h', 
                         color_discrete_sequence=['#FF8C00'], text='count')
        fig_mot.update_traces(textposition='outside')
        st.plotly_chart(fig_mot, use_container_width=True)
    else:
        st.write("Sem afastamentos registrados para este filtro.")

with col_right:
    st.subheader("🏢 Colaboradores por Empresa")
    # Gráfico de pizza mostrando Valor Absoluto e Porcentagem
    fig_pie = px.pie(df_a_filt, names=col_emp_adm, hole=0.4)
    fig_pie.update_traces(textinfo='value+percent', textposition='inside')
    st.plotly_chart(fig_pie, use_container_width=True)

# Tabela detalhada oculta sob um menu expansível
with st.expander("📋 Ver Lista Detalhada de Afastados"):
    st.dataframe(df_af_mes)
