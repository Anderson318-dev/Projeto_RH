import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
# Configura o título que aparece na aba do navegador e define o layout como 'wide' (tela cheia)
st.set_page_config(page_title="Dashboard RH Integrado", layout="wide")

# --- 2. FUNÇÃO DE PROCESSAMENTO DE DADOS ---
# O decorador @st.cache_data evita que o Python reprocesse o arquivo Excel toda vez que você mudar um filtro
@st.cache_data
def carregar_dados(file):
    try:
        # Lê o arquivo Excel enviado pelo usuário
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names
        
        # Procura as abas necessárias buscando por palavras-chave (ignora maiúsculas/minúsculas)
        aba_t = next((s for s in lista_abas if 'turn' in s.lower()), None)
        aba_a = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if 'afast' in s.lower()), None)

        # Transforma as abas encontradas em DataFrames (tabelas) do Pandas
        df_turnover = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        # Se não houver aba de afastamento, cria uma tabela vazia para não quebrar o código
        df_af_raw = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        # Padroniza os nomes das colunas: remove espaços extras e coloca tudo em minúsculo
        df_turnover.columns = df_turnover.columns.str.strip().str.lower()
        df_admitidos.columns = df_admitidos.columns.str.strip().str.lower()
        df_af_raw.columns = df_af_raw.columns.str.strip().str.lower()

        # --- MAPEAMENTO DINÂMICO DE COLUNAS (Afastamento) ---
        # Identifica as colunas de data e motivo mesmo que o nome varie (ex: 'Início' ou 'Data Inicio')
        cols_af = df_af_raw.columns
        c_ini = next((c for c in cols_af if 'inicio' in c or 'início' in c or 'dt_ini' in c), None)
        c_fim = next((c for c in cols_af if 'término' in c or 'termino' in c or 'fim' in c), None)
        c_mot = next((c for c in cols_af if 'tipo' in c or 'motivo' in c), None)
        c_emp = next((c for c in cols_af if 'empresa' in c or 'unidade' in c), None)

        # Cria colunas temporárias caso o mapeamento falhe, evitando erros de execução
        if not c_ini: df_af_raw['data_inicio_temp'] = pd.NaT; c_ini = 'data_inicio_temp'
        if not c_fim: df_af_raw['data_término_temp'] = pd.NaT; c_fim = 'data_fim_temp'
        if not c_mot: df_af_raw['motivo_temp'] = "Não Informado"; c_mot = 'motivo_temp'
        if not c_emp: df_af_raw['empresa_temp'] = "Geral"; c_emp = 'empresa_temp'

        # Converte as colunas identificadas para o formato de DATA do Python
        df_af_raw[c_ini] = pd.to_datetime(df_af_raw[c_ini], errors='coerce')
        df_af_raw[c_fim] = pd.to_datetime(df_af_raw[c_fim], errors='coerce')

        # --- TRATAMENTO DA ABA TURNOVER ---
        # Localiza a coluna de mês/ano
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        # Remove linhas que não possuem data válida
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        # Extrai o ano e cria uma coluna formatada (ex: 01 - Jan) para os filtros
        df_turnover['ano'] = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
        
        # Garante que as colunas métricas sejam tratadas como números (substitui erros por 0)
        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        return df_turnover, df_admitidos, df_af_raw, (c_ini, c_fim, c_mot, c_emp)

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return None

# --- 3. BARRA LATERAL: IMPORTAÇÃO E FILTROS ---
st.sidebar.header("📁 Base de Dados")
# Cria o botão de upload na barra lateral
arquivo_subido = st.sidebar.file_uploader("Importar BI_RH.xlsx", type=["xlsx"])

# O Dashboard só será desenhado se o usuário subir um arquivo
if arquivo_subido is not None:
    # Chama a função de carregamento
    dados = carregar_dados(arquivo_subido)
    
    if dados:
        df_t, df_a, df_af, cols_map_af = dados
        c_ini, c_fim, c_mot, c_emp_af = cols_map_af

        st.sidebar.markdown("---")
        st.sidebar.header("Filtros")

        # Filtro de Empresa: Pega a lista única de empresas da aba de admitidos
        col_emp_adm = 'empresa' if 'empresa' in df_a.columns else df_a.columns[0]
        lista_empresas = sorted([x for x in df_a[col_emp_adm].unique() if str(x) != 'nan'])
        empresa_sel = st.sidebar.multiselect("Empresas", options=lista_empresas, default=lista_empresas)

        # Filtro de Ano e Mês: Baseado na aba de Turnover
        lista_anos = sorted(df_t['ano'].unique(), reverse=True)
        ano_sel = st.sidebar.selectbox("Ano de Referência", lista_anos)
        df_meses_ano = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel = st.sidebar.selectbox("Mês de Referência", df_meses_ano['mes_nome'].unique())

        # --- 4. LÓGICA DE FILTRAGEM E CÁLCULOS ---
        # Define a data de início e fim do mês selecionado para cálculos de afastamento
        data_ref = df_meses_ano[df_meses_ano['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        fim_mes_ref = data_ref + pd.offsets.MonthEnd(0)

        # Filtra dados de evolução para o ano selecionado
        df_t_ano = df_t[df_t['ano'] == ano_sel].copy().sort_values('mês_ano')

        # Cálculo da Taxa de Turnover (Fórmula: ((Adm + Desl) / 2) / Efetivo)
        df_t_ano['turnover_taxa'] = (
            ((df_t_ano['admissões'] + df_t_ano['desligamentos']) / 2) / 
            df_t_ano['colaboradores'].replace(0, 1) # Evita divisão por zero
        ) * 100

        # Filtra os dados específicos do mês selecionado para os KPIs
        df_t_periodo = df_t_ano[df_t_ano['mes_nome'] == mes_sel]
        df_a_filt = df_a[df_a[col_emp_adm].isin(empresa_sel)]

        # Filtra afastados que estavam ativos no mês de referência
        mask_afastados = (df_af[c_ini] <= fim_mes_ref) & ((df_af[c_fim].isnull()) | (df_af[c_fim] >= data_ref))
        df_af_mes = df_af[mask_afastados]
        
        # Filtra afastados por empresa se a coluna existir
        if c_emp_af in df_af_mes.columns:
            df_af_mes = df_af_mes[df_af_mes[c_emp_af].isin(empresa_sel)]

        # --- 5. INTERFACE DO DASHBOARD ---
        st.title(f"📊 Dashboard RH - {mes_sel}/{ano_sel}")

        # Linha de KPIs (Cards de resumo)
        metrica1, metrica2, metrica3, metrica4 = st.columns(4)
        if not df_t_periodo.empty:
            linha = df_t_periodo.iloc[0]
            metrica1.metric("Efetivo Total", int(linha['colaboradores']))
            metrica2.metric("Admissões", int(linha['admissões']))
            metrica3.metric("Desligamentos", int(linha['desligamentos']))
            metrica4.metric("Taxa Turnover", f"{linha['turnover_taxa']:.2f}%")

        st.markdown("---")

        # Gráfico de Barras e Linhas (Evolução Mensal)
        st.subheader("📈 Movimentação Mensal vs Total Efetivos")
        fig_evol = go.Figure()
        # Adiciona barras de Admissões
        fig_evol.add_trace(go.Bar(x=df_t_ano['mes_nome'], y=df_t_ano['admissões'], name='Admissões', marker_color='#2ecc71'))
        # Adiciona barras de Desligamentos
        fig_evol.add_trace(go.Bar(x=df_t_ano['mes_nome'], y=df_t_ano['desligamentos'], name='Desligamentos', marker_color='#e74c3c'))
        # Adiciona linha de Efetivo (usando o eixo Y da direita)
        fig_evol.add_trace(go.Scatter(x=df_t_ano['mes_nome'], y=df_t_ano['colaboradores'], name='Efetivo Total', yaxis='y2', line=dict(color='#3498db', width=3)))
        
        fig_evol.update_layout(
            yaxis=dict(title="Qtd Movimentação"),
            yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
            barmode='group',
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_evol, use_container_width=True)

        # Colunas Inferiores: Afastamentos e Distribuição por Empresa
        col_graf_1, col_graf_2 = st.columns(2)
        
        with col_graf_1:
            st.subheader("🥪 Motivos de Afastamento")
            if not df_af_mes.empty:
                resumo_mot = df_af_mes[c_mot].value_counts().reset_index()
                fig_bar_af = px.bar(resumo_mot, x='count', y=c_mot, orientation='h', color_discrete_sequence=['#FF8C00'])
                st.plotly_chart(fig_bar_af, use_container_width=True)
            else:
                st.write("Nenhum afastamento no período.")

        with col_graf_2:
            st.subheader("🏢 Colaboradores por Empresa")
            fig_pizza = px.pie(df_a_filt, names=col_emp_adm, hole=0.4)
            st.plotly_chart(fig_pizza, use_container_width=True)

        # Tabela detalhada opcional
        with st.expander("📋 Detalhes dos Afastados (Tabela)"):
            st.dataframe(df_af_mes)

else:
    # Tela exibida enquanto o usuário não faz o upload
    st.info("Para começar, por favor carregue o arquivo Excel na barra lateral esquerda.")
    st.markdown("""
    **Instruções para o arquivo:**
    1. Certifique-se que o arquivo possui as abas: *Turnover*, *Admitidos* e *Afastamentos*.
    2. O arquivo deve estar no formato `.xlsx`.
    """)
