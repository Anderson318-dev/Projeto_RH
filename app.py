import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")

@st.cache_data
def carregar_dados(file):
    try:
        # Lê o arquivo Excel enviado
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names
        
        # Localização dinâmica das abas (ignora maiúsculas/minúsculas)
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        # Criação dos DataFrames
        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Padronização de nomes de colunas (letras minúsculas e sem espaços)
        for df in [df_turnover, df_admitidos, df_af_raw]:
            df.columns = df.columns.str.strip().str.lower()

        # Mapeamento de colunas de Afastamento (Datas e Motivos)
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)

        # Tratamento de Datas no Turnover
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        # Garante colunas numéricas para os cálculos
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        # Cálculo da Taxa de Turnover
        df_turnover['turnover_taxa'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / 
                                        df_turnover['colaboradores'].replace(0, 1)) * 100

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot)
    except Exception as e:
        st.error(f"Erro ao processar arquivo: {e}")
        return None

# --- 2. BARRA LATERAL (IMPORTAÇÃO E FILTROS) ---
st.sidebar.header("📁 Importação")
arquivo_subido = st.sidebar.file_uploader("Selecione o BI_RH.xlsx", type=["xlsx"])

if arquivo_subido:
    dados = carregar_dados(arquivo_subido)
    if dados:
        df_t, df_a, df_af, (c_ini, c_fim, c_mot) = dados

        # Filtros de Ano e Mês
        ano_sel = st.sidebar.selectbox("Ano", sorted(df_t['ano'].unique(), reverse=True))
        df_meses_filtrados = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel = st.sidebar.selectbox("Mês", df_meses_filtrados['mes_nome'].unique())

        # Identificação de Mês Atual vs Anterior para o Delta
        data_atual = df_meses_filtrados[df_meses_filtrados['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        data_ant = data_atual - pd.DateOffset(months=1)
        
        df_atual = df_t[df_t['mês_ano'] == data_atual].iloc[0]
        df_ant_list = df_t[df_t['mês_ano'] == data_ant]
        df_ant = df_ant_list.iloc[0] if not df_ant_list.empty else None

        # --- 3. TÍTULO E KPIs ---
        st.title(f"📊 Dashboard de Indicadores RH - {mes_sel}/{ano_sel}")
        
        # Função simples para calcular variação
        def calc_delta(val, col): return (val - df_ant[col]) if df_ant is not None else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Efetivo Total", int(df_atual['colaboradores']), delta=int(calc_delta(df_atual['colaboradores'], 'colaboradores')))
        c2.metric("Admissões", int(df_atual['admissões']), delta=int(calc_delta(df_atual['admissões'], 'admissões')))
        # Delta invertido: se desligamento sobe, fica vermelho
        c3.metric("Desligamentos", int(df_atual['desligamentos']), delta=int(calc_delta(df_atual['desligamentos'], 'desligamentos')), delta_color="inverse")
        c4.metric("Taxa Turnover", f"{df_atual['turnover_taxa']:.2f}%", delta=f"{calc_delta(df_atual['turnover_taxa'], 'turnover_taxa'):.2f}%", delta_color="inverse")

        st.markdown("---")

        # --- 4. GRÁFICO DE EVOLUÇÃO (COM RÓTULOS SUPERIORES) ---
        st.subheader("📈 Evolução da Movimentação Mensal")
        df_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        
        fig_evol = go.Figure()
        # Admissões (Barras Verdes)
        fig_evol.add_trace(go.Bar(x=df_ano['mes_nome'], y=df_ano['admissões'], name='Admissões', 
                                 marker_color='#27ae60', text=df_ano['admissões'], textposition='outside'))
        # Desligamentos (Barras Vermelhas)
        fig_evol.add_trace(go.Bar(x=df_ano['mes_nome'], y=df_ano['desligamentos'], name='Desligamentos', 
                                 marker_color='#c0392b', text=df_ano['desligamentos'], textposition='outside'))
        # Efetivo (Linha Azul no eixo secundário)
        fig_evol.add_trace(go.Scatter(x=df_ano['mes_nome'], y=df_ano['colaboradores'], name='Efetivo', 
                                     yaxis='y2', line=dict(color='#2980b9', width=4), 
                                     mode='lines+markers+text', text=df_ano['colaboradores'], textposition='top center'))

        fig_evol.update_layout(
            yaxis=dict(title="Quantidade"),
            yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
            barmode='group',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig_evol, use_container_width=True)

        st.markdown("---")

        # --- 5. SEÇÃO DE AFASTAMENTOS ---
        col_resumo, col_grafico = st.columns([1, 2])
        
        # Filtro de afastados ativos no mês selecionado
        fim_mes = data_atual + pd.offsets.MonthEnd(0)
        mask_af = (df_af[c_ini] <= fim_mes) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_atual))
        df_af_mes = df_af[mask_af]

        with col_resumo:
            st.subheader("📋 Resumo de Absenteísmo")
            # Apresentação clara da QUANTIDADE de afastados
            st.metric("Total de Afastados no Mês", len(df_af_mes))
            st.info("Este KPI conta quantos colaboradores estiveram afastados (parcial ou totalmente) durante o mês de referência.")

        with col_grafico:
            st.subheader("Principais Motivos de Afastamento")
            if not df_af_mes.empty:
                resumo_af = df_af_mes[c_mot].value_counts().reset_index()
                # Gráfico com rótulos de dados superiores (nas pontas das barras)
                fig_af = px.bar(resumo_af, x='count', y=c_mot, orientation='h', 
                               text='count', color_discrete_sequence=['#8e44ad'])
                fig_af.update_traces(textposition='outside')
                st.plotly_chart(fig_af, use_container_width=True)
            else:
                st.write("Sem registros de afastamento para este período.")

        # Detalhamento em tabela
        with st.expander("Ver lista completa de afastados"):
            st.dataframe(df_af_mes, use_container_width=True)

else:
    st.info("Aguardando importação da planilha BI_RH.xlsx.")
