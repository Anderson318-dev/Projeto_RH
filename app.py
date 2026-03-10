import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH Pro", layout="wide")

@st.cache_data
def carregar_dados(file):
    try:
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names
        
        # Localização automática das abas por palavra-chave
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Limpeza de nomes de colunas
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_af_raw.columns = df_af_raw.columns.str.strip().str.lower()

        # Mapeamento de colunas de afastamento
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)
        c_emp = next((c for c in cols_af if 'empresa' in c or 'unidade' in c), None)

        # Datas e tratamento de números no Turnover
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        # Cálculo da Taxa de Turnover (Fórmula padrão)
        df_turnover['turnover_taxa'] = (
            ((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) / 
            df_turnover['colaboradores'].replace(0, 1)
        ) * 100

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot, c_emp)
    except Exception as e:
        st.error(f"Erro no processamento: {e}")
        return None

# --- 2. INTERFACE DE IMPORTAÇÃO ---
st.sidebar.header("📁 Upload de Dados")
arquivo_subido = st.sidebar.file_uploader("Arraste o BI_RH.xlsx aqui", type=["xlsx"])

if arquivo_subido is not None:
    dados = carregar_dados(arquivo_subido)
    
    if dados:
        df_t, df_a, df_af, cols_map_af = dados
        c_ini, c_fim, c_mot, c_emp_af = cols_map_af

        # --- 3. FILTROS ---
        st.sidebar.markdown("---")
        lista_anos = sorted(df_t['ano'].unique(), reverse=True)
        ano_sel = st.sidebar.selectbox("Ano", lista_anos)
        
        df_meses_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel = st.sidebar.selectbox("Mês", df_meses_ano['mes_nome'].unique())

        # --- 4. LÓGICA DE COMPARAÇÃO (DELTA) ---
        # Pegamos a data do mês atual selecionado
        data_atual = df_meses_ano[df_meses_ano['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        # Calculamos a data do mês imediatamente anterior (ex: se selecionou Março, busca Fevereiro)
        data_anterior = data_atual - pd.DateOffset(months=1)

        # Filtramos a linha do mês atual e a linha do mês anterior para comparar
        df_mes_atual = df_t[df_t['mês_ano'] == data_atual]
        df_mes_anterior = df_t[df_t['mês_ano'] == data_anterior]

        # Função interna para calcular a diferença (delta)
        def calcular_delta(coluna):
            if not df_mes_atual.empty and not df_mes_anterior.empty:
                val_atual = df_mes_atual[coluna].iloc[0]
                val_ant = df_mes_anterior[coluna].iloc[0]
                return val_atual - val_ant
            return 0

        # --- 5. EXIBIÇÃO DOS KPIs COM DELTA ---
        st.title(f"📊 Gestão de RH - {mes_sel}/{ano_sel}")
        
        c1, c2, c3, c4 = st.columns(4)
        
        if not df_mes_atual.empty:
            curr = df_mes_atual.iloc[0]
            
            # st.metric mostra o valor principal e a variação (delta) em relação ao mês anterior
            c1.metric("Efetivo Total", int(curr['colaboradores']), delta=int(calcular_delta('colaboradores')))
            c2.metric("Admissões", int(curr['admissões']), delta=int(calcular_delta('admissões')))
            # Para desligamentos, o delta positivo geralmente é "ruim" (vermelho), então invertemos a cor
            c3.metric("Desligamentos", int(curr['desligamentos']), delta=int(calcular_delta('desligamentos')), delta_color="inverse")
            c4.metric("Taxa Turnover", f"{curr['turnover_taxa']:.2f}%", delta=f"{calcular_delta('turnover_taxa'):.2f}%", delta_color="inverse")

        st.markdown("---")

        # --- 6. GRÁFICOS ---
        # Container para organizar o gráfico principal
        with st.container():
            st.subheader("📈 Tendência Anual de Movimentação")
            df_ano_plot = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
            
            fig = go.Figure()
            # Barras agrupadas
            fig.add_trace(go.Bar(x=df_ano_plot['mes_nome'], y=df_ano_plot['admissões'], name='Admissões', marker_color='#2ecc71'))
            fig.add_trace(go.Bar(x=df_ano_plot['mes_nome'], y=df_ano_plot['desligamentos'], name='Desligamentos', marker_color='#e74c3c'))
            # Linha de Efetivo no eixo secundário
            fig.add_trace(go.Scatter(x=df_ano_plot['mes_nome'], y=df_ano_plot['colaboradores'], name='Efetivo', yaxis='y2', line=dict(color='#3498db', width=4)))
            
            fig.update_layout(
                yaxis=dict(title="Movimentações"),
                yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
                barmode='group',
                legend=dict(orientation="h", y=1.1)
            )
            st.plotly_chart(fig, use_container_width=True)

        # Colunas para os gráficos de pizza e barras horizontais
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.subheader("🏢 Distribuição por Empresa")
            # Filtro de empresa aplicado apenas aqui e nos detalhes
            col_emp = 'empresa' if 'empresa' in df_a.columns else df_a.columns[0]
            fig_pie = px.pie(df_a, names=col_emp, hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_b:
            st.subheader("🥪 Principais Motivos de Afastamento")
            # Lógica de filtragem de data para afastados (quem estava afastado naquele mês)
            fim_mes = data_atual + pd.offsets.MonthEnd(0)
            mask = (df_af[c_ini] <= fim_mes) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_atual))
            df_af_filtrado = df_af[mask]
            
            if not df_af_filtrado.empty:
                contagem = df_af_filtrado[c_mot].value_counts().reset_index()
                fig_af = px.bar(contagem, x='count', y=c_mot, orientation='h', color_discrete_sequence=['#9b59b6'])
                st.plotly_chart(fig_af, use_container_width=True)
            else:
                st.info("Sem afastamentos registrados para este período.")

        # Rodapé com tabela detalhada
        with st.expander("🔍 Explorar Dados Brutos (Afastados)"):
            st.dataframe(df_af_filtrado, use_container_width=True)

else:
    # Mensagem de boas-vindas com guia rápido
    st.info("👋 Bem-vindo! Para visualizar as análises, importe o arquivo BI_RH.xlsx na barra lateral.")
