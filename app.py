import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados():
    try:
        xls = pd.ExcelFile("BI_RH.xlsx")
        lista_abas = xls.sheet_names
        
        # 1. Localizar Abas
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_afast_raw = pd.read_excel(xls, sheet_name=aba_af)

        # Padronização inicial
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_afast_raw.columns = df_afast_raw.columns.str.strip().str.lower()

        # --- MAPEAMENTO DINÂMICO DE COLUNAS (AFASTADOS) ---
        cols_af = df_afast_raw.columns
        # Procura a melhor coluna para cada campo
        col_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_inicio' in c), None)
        col_fim = next((c for c in cols_af if 'fim' in c or 'termino' in c or 'término' in c), None)
        col_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c or 'desc' in c), None)
        col_emp = next((c for c in cols_af if 'empresa' in c or 'unidade' in c), None)
        col_nom = next((c for c in cols_af if 'nome' in c or 'funcionario' in c), None)

        # Validação crítica
        if not col_ini:
            st.error(f"Coluna de 'Data Início' não encontrada na aba {aba_af}. Colunas lidas: {list(cols_af)}")
            st.stop()

        # Renomeia para nomes padrão internos para facilitar o código
        mapa = {col_ini: 'data_inicio', col_fim: 'data_fim', col_mot: 'motivo', col_emp: 'empresa', col_nom: 'nome'}
        df_afastados = df_afast_raw.rename(columns=mapa)

        # Tratamento de Datas
        df_afastados['data_inicio'] = pd.to_datetime(df_afastados['data_inicio'], errors='coerce')
        df_afastados['data_fim'] = pd.to_datetime(df_afastados['data_fim'], errors='coerce')
        
        # Tratamento Turnover
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')

        return df_turnover, df_admitidos, df_afastados

    except Exception as e:
        st.error(f"Erro Crítico: {e}")
        st.stop()

df_t, df_a, df_af = carregar_dados()

# --- SIDEBAR ---
st.sidebar.header("Filtros")
lista_anos = sorted(df_t['ano'].unique(), reverse=True)
ano_sel = st.sidebar.selectbox("Ano", lista_anos)

df_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
mes_sel = st.sidebar.selectbox("Mês", df_meses['mes_nome'].unique())

# --- LÓGICA DE CÁLCULO MENSAL ---
# Pega o primeiro dia do mês selecionado
data_ref = df_meses[df_meses['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
# Pega o último dia do mês
fim_mes = data_ref + pd.offsets.MonthEnd(0)

# Filtrar quem estava afastado DENTRO desse mês
# Começou antes do fim do mês E (Não terminou ainda OU terminou depois que o mês começou)
mask = (df_af['data_inicio'] <= fim_mes) & (
    (df_af['data_fim'].isnull()) | (df_af['data_fim'] >= data_ref)
)
df_af_mes = df_af[mask]

# --- DASHBOARD ---
st.title(f"📊 Dashboard de Afastamentos - {mes_sel}/{ano_sel}")

# KPIs
c1, c2 = st.columns(2)
with c1:
    st.metric("Total de Afastados no Período", len(df_af_mes))
with c2:
    motivo_topo = df_af_mes['motivo'].value_counts().index[0] if not df_af_mes.empty else "N/A"
    st.metric("Principal Motivo", motivo_topo)

st.markdown("---")
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.subheader("🥪 Afastados por Motivo")
    if not df_af_mes.empty:
        fig_mot = px.bar(df_af_mes['motivo'].value_counts().reset_index(), 
                         x='count', y='motivo', orientation='h', color_discrete_sequence=['#ef553b'])
        st.plotly_chart(fig_mot, use_container_width=True)

with col_graf2:
    st.subheader("🏢 Afastados por Empresa")
    if not df_af_mes.empty and 'empresa' in df_af_mes.columns:
        fig_emp = px.pie(df_af_mes, names='empresa', hole=0.4)
        st.plotly_chart(fig_emp, use_container_width=True)

# Evolução
st.markdown("---")
st.subheader("📈 Evolução de Afastamentos no Ano")
evolucao = []
for m in df_meses['mês_ano']:
    f_m = m + pd.offsets.MonthEnd(0)
    qtd = len(df_af[(df_af['data_inicio'] <= f_m) & ((df_af['data_fim'].isnull()) | (df_af['data_fim'] >= m))])
    evolucao.append(qtd)

df_meses['qtd_afastados'] = evolucao
fig_line = px.line(df_meses, x='mes_nome', y='qtd_afastados', markers=True, line_shape='spline')
st.plotly_chart(fig_line, use_container_width=True)

with st.expander("📋 Detalhes dos Afastados (Mês Selecionado)"):
    st.write(df_af_mes)
