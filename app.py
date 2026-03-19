import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
from pathlib import Path
from datetime import date

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Dashboard RH - Pro Security", layout="wide")

# --- LOGO ---
def get_logo_base64():
    logo_path = Path(__file__).parent / "Logo_Pro_Security_Horizontal.jpg"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

logo_b64 = get_logo_base64()

st.markdown("""
<style>
    .logo-container { display: flex; align-items: center; padding: 10px 0 20px 0; }
    .logo-container img { height: 60px; object-fit: contain; }
    .header-divider { border-top: 3px solid #c0392b; margin-bottom: 20px; }
    .badge-aberto {
        background-color: #e74c3c; color: white;
        padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;
    }
    .badge-futuro {
        background-color: #f39c12; color: white;
        padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

if logo_b64:
    st.markdown(
        f'<div class="logo-container"><img src="data:image/jpeg;base64,{logo_b64}" alt="Pro Security Logo"/></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="header-divider"></div>', unsafe_allow_html=True)
else:
    st.markdown("## 🔒 Pro Security")
    st.markdown('<div class="header-divider"></div>', unsafe_allow_html=True)


@st.cache_data
def carregar_dados(file):
    try:
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names

        # --- LOCALIZAÇÃO DAS ABAS ---
        aba_t   = next((s for s in lista_abas if 'turn'   in s.lower()), None)
        aba_adm = next((s for s in lista_abas if 'admit'  in s.lower() or 'adm' in s.lower()), None)
        aba_dem = next((s for s in lista_abas if 'demit'  in s.lower() or 'deslig' in s.lower()), None)
        aba_af  = next((s for s in lista_abas if 'afast'  in s.lower()), None)

        df_turnover  = pd.read_excel(xls, sheet_name=aba_t)   if aba_t   else pd.DataFrame()
        df_admitidos = pd.read_excel(xls, sheet_name=aba_adm) if aba_adm else pd.DataFrame()
        df_demitidos = pd.read_excel(xls, sheet_name=aba_dem) if aba_dem else pd.DataFrame()
        df_af_raw    = pd.read_excel(xls, sheet_name=aba_af)  if aba_af  else pd.DataFrame()

        for df in [df_turnover, df_admitidos, df_demitidos, df_af_raw]:
            if not df.empty:
                df.columns = df.columns.str.strip().str.lower()

        # --- COLUNAS DE AFASTAMENTO ---
        c_ini = c_fim = c_mot = c_emp_af = None
        if not df_af_raw.empty:
            cols = df_af_raw.columns
            c_ini    = next((c for c in cols if 'inicio' in c or 'início' in c or 'dt_ini' in c or 'início' in c), None)
            c_fim    = next((c for c in cols if 'término' in c or 'termino' in c or 'fim' in c or 'término' in c), None)
            c_mot    = next((c for c in cols if 'tipo' in c or 'motivo' in c), None)
            c_emp_af = next((c for c in cols if 'empresa' in c or 'company' in c or 'unidade' in c), None)

            # Converter datas
            if c_ini:
                df_af_raw[c_ini] = pd.to_datetime(df_af_raw[c_ini], errors='coerce')
            if c_fim:
                df_af_raw[c_fim] = pd.to_datetime(df_af_raw[c_fim], errors='coerce')

            # --- CÁLCULO DE TEMPO DE AFASTAMENTO ---
            hoje = pd.Timestamp(date.today())
            if c_ini:
                data_ref_fim = df_af_raw[c_fim].fillna(hoje)
                df_af_raw['dias_afastamento'] = (data_ref_fim - df_af_raw[c_ini]).dt.days.clip(lower=0)

            # --- STATUS DO AFASTAMENTO ---
            def classificar_status(row):
                fim = row.get(c_fim) if c_fim else None
                if pd.isnull(fim):
                    return '🔴 Em aberto'
                elif pd.Timestamp(fim) > hoje:
                    return '🟡 Data futura'
                else:
                    return '🟢 Encerrado'

            df_af_raw['status_afastamento'] = df_af_raw.apply(classificar_status, axis=1)

        # --- COLUNAS DE EMPRESA (admitidos / demitidos) ---
        c_emp_adm = None
        c_emp_dem = None
        c_data_adm = None
        c_data_dem = None

        if not df_admitidos.empty:
            c_emp_adm  = next((c for c in df_admitidos.columns if 'empresa' in c or 'company' in c or 'unidade' in c), None)
            c_data_adm = next((c for c in df_admitidos.columns if 'admis' in c or 'data' in c or 'dt_' in c or 'mês' in c or 'mes' in c), None)
            if c_data_adm:
                df_admitidos[c_data_adm] = pd.to_datetime(df_admitidos[c_data_adm], errors='coerce')
                df_admitidos['ano_adm']  = df_admitidos[c_data_adm].dt.year
                df_admitidos['mes_adm']  = df_admitidos[c_data_adm].dt.month
                df_admitidos['mes_nome'] = df_admitidos[c_data_adm].dt.strftime('%m - %b')

        if not df_demitidos.empty:
            c_emp_dem  = next((c for c in df_demitidos.columns if 'empresa' in c or 'company' in c or 'unidade' in c), None)
            c_data_dem = next((c for c in df_demitidos.columns if 'demis' in c or 'deslig' in c or 'data' in c or 'dt_' in c or 'mês' in c or 'mes' in c), None)
            if c_data_dem:
                df_demitidos[c_data_dem] = pd.to_datetime(df_demitidos[c_data_dem], errors='coerce')
                df_demitidos['ano_dem']  = df_demitidos[c_data_dem].dt.year
                df_demitidos['mes_dem']  = df_demitidos[c_data_dem].dt.month
                df_demitidos['mes_nome'] = df_demitidos[c_data_dem].dt.strftime('%m - %b')

        # --- ABA TURNOVER (KPIs globais) ---
        if not df_turnover.empty:
            col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
            df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
            df_turnover = df_turnover.dropna(subset=['mês_ano'])
            df_turnover['periodo']  = df_turnover['mês_ano'].dt.to_period('M')
            df_turnover['ano']      = df_turnover['mês_ano'].dt.year.astype(int)
            df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')
            for c in ['admissões', 'desligamentos', 'colaboradores']:
                if c in df_turnover.columns:
                    df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)
            df_turnover['turnover_taxa'] = (((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) /
                                             df_turnover['colaboradores'].replace(0, 1)) * 100
            df_turnover['retencao_taxa'] = (df_turnover['desligamentos'] /
                                             df_turnover['colaboradores'].replace(0, 1)) * 100

        return (df_turnover, df_admitidos, df_demitidos, df_af_raw,
                (c_ini, c_fim, c_mot, c_emp_af),
                (c_emp_adm, c_data_adm, c_emp_dem, c_data_dem))

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None


# --- 2. SIDEBAR ---
if logo_b64:
    st.sidebar.image(f"data:image/jpeg;base64,{logo_b64}", use_column_width=True)

st.sidebar.header("📁 Importação")
arquivo_subido = st.sidebar.file_uploader("Selecione o BI_RH.xlsx", type=["xlsx"])

if arquivo_subido:
    dados = carregar_dados(arquivo_subido)
    if dados:
        df_t, df_adm, df_dem, df_af, (c_ini, c_fim, c_mot, c_emp_af), (c_emp_adm, c_data_adm, c_emp_dem, c_data_dem) = dados

        # --- FILTRO DE ANO/MÊS (baseado na aba Turnover) ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("📅 Período")
        ano_sel = st.sidebar.selectbox("Ano", sorted(df_t['ano'].unique(), reverse=True))
        df_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel  = st.sidebar.selectbox("Mês", df_meses['mes_nome'].unique())

        # Período selecionado
        data_sel    = df_meses[df_meses['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        per_atual   = data_sel.to_period('M')
        per_anterior = (data_sel - pd.DateOffset(months=1)).to_period('M')
        data_fim_mes = data_sel + pd.offsets.MonthEnd(0)

        row_atual    = df_t[df_t['periodo'] == per_atual].iloc[0]
        row_ant_list = df_t[df_t['periodo'] == per_anterior]
        row_ant      = row_ant_list.iloc[0] if not row_ant_list.empty else None

        # --- FILTRO DE EMPRESA (para gráficos específicos) ---
        st.sidebar.markdown("---")
        st.sidebar.subheader("🏢 Filtro por Empresa")
        st.sidebar.caption("Aplica-se à Evolução Mensal, Absenteísmo e Motivos de Afastamento.")

        # Coletar empresas das abas admitidos, demitidos e afastados
        emp_adm = sorted(df_adm[c_emp_adm].dropna().unique().tolist()) if (c_emp_adm and not df_adm.empty) else []
        emp_dem = sorted(df_dem[c_emp_dem].dropna().unique().tolist()) if (c_emp_dem and not df_dem.empty) else []
        emp_af  = sorted(df_af[c_emp_af].dropna().unique().tolist())   if (c_emp_af  and not df_af.empty)  else []
        todas_empresas = sorted(set(emp_adm + emp_dem + emp_af))

        if todas_empresas:
            empresa_sel = st.sidebar.selectbox("Empresa", ["Todas as Empresas"] + todas_empresas)
        else:
            empresa_sel = "Todas as Empresas"
            st.sidebar.info("Coluna 'empresa' não encontrada nas abas de movimentação.")

        # Aplicar filtro de empresa
        def filtrar_empresa(df, col_emp):
            if empresa_sel != "Todas as Empresas" and col_emp and col_emp in df.columns:
                return df[df[col_emp] == empresa_sel].copy()
            return df.copy()

        df_adm_f = filtrar_empresa(df_adm, c_emp_adm)
        df_dem_f = filtrar_empresa(df_dem, c_emp_dem)
        df_af_f  = filtrar_empresa(df_af,  c_emp_af)

        label_emp = f" — {empresa_sel}" if empresa_sel != "Todas as Empresas" else " — Todas as Empresas"

        # =========================================================
        # --- 3. KPIs GLOBAIS (SEM FILTRO POR EMPRESA) ---
        # =========================================================
        st.title(f"📊 INDICADORES RH — {mes_sel} / {ano_sel}")
        st.caption("Os KPIs abaixo refletem os totais consolidados (todas as empresas).")

        def calc_delta(val_atual, col):
            return (val_atual - row_ant[col]) if row_ant is not None else None

        msg_ajuda = "Comparação com o mês anterior. Cores: Verde (Melhora) e Vermelho (Atenção)."

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Efetivo", int(row_atual['colaboradores']),
                  delta=calc_delta(row_atual['colaboradores'], 'colaboradores'), help=msg_ajuda)
        c2.metric("Admissões", int(row_atual['admissões']),
                  delta=calc_delta(row_atual['admissões'], 'admissões'), help=msg_ajuda)
        c3.metric("Desligamentos", int(row_atual['desligamentos']),
                  delta=calc_delta(row_atual['desligamentos'], 'desligamentos'),
                  delta_color="inverse", help=msg_ajuda)
        c4.metric("Taxa Turnover", f"{row_atual['turnover_taxa']:.2f}%",
                  delta=f"{calc_delta(row_atual['turnover_taxa'], 'turnover_taxa'):.2f}%" if row_ant is not None else None,
                  delta_color="inverse", help=msg_ajuda)
        c5.metric("Taxa Retenção", f"{row_atual['retencao_taxa']:.2f}%",
                  delta=f"{calc_delta(row_atual['retencao_taxa'], 'retencao_taxa'):.2f}%" if row_ant is not None else None,
                  delta_color="inverse", help=msg_ajuda)

        st.markdown("---")

        # =========================================================
        # --- 4. EVOLUÇÃO DA MOVIMENTAÇÃO MENSAL (COM FILTRO) ---
        # =========================================================
        st.subheader(f"📈 Evolução da Movimentação Mensal{label_emp}")

        if not df_adm_f.empty and c_data_adm and not df_dem_f.empty and c_data_dem:
            # Conta admitidos por mês/ano
            adm_grupo = (df_adm_f[df_adm_f['ano_adm'] == ano_sel]
                         .groupby('mes_nome', sort=False)
                         .size().reset_index(name='admissões'))
            # Conta demitidos por mês/ano
            dem_grupo = (df_dem_f[df_dem_f['ano_dem'] == ano_sel]
                         .groupby('mes_nome', sort=False)
                         .size().reset_index(name='desligamentos'))

            # Meses do ano ordenados
            todos_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')['mes_nome'].tolist()
            df_mov = pd.DataFrame({'mes_nome': todos_meses})
            df_mov = df_mov.merge(adm_grupo, on='mes_nome', how='left')
            df_mov = df_mov.merge(dem_grupo, on='mes_nome', how='left')
            df_mov = df_mov.fillna(0)

            fig_mov = go.Figure()
            fig_mov.add_trace(go.Bar(
                x=df_mov['mes_nome'], y=df_mov['admissões'], name='Admissões',
                marker_color='#2ecc71', text=df_mov['admissões'].astype(int), textposition='outside'
            ))
            fig_mov.add_trace(go.Bar(
                x=df_mov['mes_nome'], y=df_mov['desligamentos'], name='Desligamentos',
                marker_color='#e74c3c', text=df_mov['desligamentos'].astype(int), textposition='outside'
            ))
            fig_mov.update_layout(
                barmode='group',
                yaxis=dict(title="Quantidade"),
                legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig_mov, use_container_width=True)
        else:
            # Fallback: usa aba turnover sem filtro de empresa
            df_ano_plot = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
            fig_mov = go.Figure()
            fig_mov.add_trace(go.Bar(x=df_ano_plot['mes_nome'], y=df_ano_plot['admissões'], name='Admissões',
                                     marker_color='#2ecc71', text=df_ano_plot['admissões'], textposition='outside'))
            fig_mov.add_trace(go.Bar(x=df_ano_plot['mes_nome'], y=df_ano_plot['desligamentos'], name='Desligamentos',
                                     marker_color='#e74c3c', text=df_ano_plot['desligamentos'], textposition='outside'))
            fig_mov.add_trace(go.Scatter(x=df_ano_plot['mes_nome'], y=df_ano_plot['colaboradores'], name='Efetivo Total',
                                         yaxis='y2', line=dict(color='#3498db', width=4), mode='lines+markers+text',
                                         text=df_ano_plot['colaboradores'].astype(int), textposition='top center'))
            fig_mov.update_layout(
                yaxis=dict(title="Volume"),
                yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
                barmode='group',
                legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
            )
            st.caption("ℹ️ Abas 'admitidos'/'demitidos' não encontradas ou sem coluna de data — exibindo dados consolidados da aba Turnover.")
            st.plotly_chart(fig_mov, use_container_width=True)

        st.markdown("---")

        # =========================================================
        # --- 5. AFASTAMENTOS (COM FILTRO DE EMPRESA) ---
        # =========================================================

        # Filtrar afastados pelo período selecionado
        if c_ini and c_fim and not df_af_f.empty:
            mask = (df_af_f[c_ini] <= data_fim_mes) & (
                (df_af_f[c_fim].isnull()) | (df_af_f[c_fim] >= data_sel)
            )
            df_af_mes = df_af_f[mask].copy()
        else:
            df_af_mes = pd.DataFrame()

        # Sub-conjuntos de status
        df_abertos  = df_af_mes[df_af_mes['status_afastamento'] == '🔴 Em aberto']  if 'status_afastamento' in df_af_mes.columns else pd.DataFrame()
        df_futuros  = df_af_mes[df_af_mes['status_afastamento'] == '🟡 Data futura'] if 'status_afastamento' in df_af_mes.columns else pd.DataFrame()

        # --- Linha de KPIs de Absenteísmo ---
        st.subheader(f"📋 Absenteísmo{label_emp}")

        ka1, ka2, ka3, ka4 = st.columns(4)
        ka1.metric("Total Afastados no Mês", len(df_af_mes))
        ka2.metric("🔴 Em Aberto", len(df_abertos), help="Afastamentos sem data de término registrada.")
        ka3.metric("🟡 Data Futura", len(df_futuros), help="Afastamentos com data de término prevista no futuro.")

        if 'dias_afastamento' in df_af_mes.columns and not df_af_mes.empty:
            media_dias = df_af_mes['dias_afastamento'].mean()
            ka4.metric("⏱️ Média de Dias", f"{media_dias:.1f} dias")
        else:
            ka4.metric("⏱️ Média de Dias", "—")

        st.info("Colaboradores com ao menos um dia de afastamento dentro do período de referência.")

        # --- Linha: Motivos + Distribuição de Dias ---
        col_mot, col_dias = st.columns([3, 2])

        with col_mot:
            st.subheader(f"Motivos de Afastamento{label_emp}")
            if not df_af_mes.empty and c_mot:
                resumo = df_af_mes[c_mot].value_counts().reset_index()
                resumo.columns = [c_mot, 'count']
                fig_af = px.bar(resumo, x='count', y=c_mot, orientation='h', text='count',
                                color_discrete_sequence=['#c0392b'])
                fig_af.update_traces(textposition='outside')
                fig_af.update_layout(yaxis_title="", xaxis_title="Quantidade")
                st.plotly_chart(fig_af, use_container_width=True)
            else:
                st.write("Sem registros para este período.")

        with col_dias:
            st.subheader("⏱️ Distribuição de Dias de Afastamento")
            if 'dias_afastamento' in df_af_mes.columns and not df_af_mes.empty:
                fig_dias = px.histogram(df_af_mes, x='dias_afastamento', nbins=15,
                                        color_discrete_sequence=['#8e44ad'],
                                        labels={'dias_afastamento': 'Dias de Afastamento'})
                fig_dias.update_layout(yaxis_title="Nº de Colaboradores", xaxis_title="Dias")
                st.plotly_chart(fig_dias, use_container_width=True)
            else:
                st.write("Dados de datas não disponíveis.")

        # --- Afastamentos em aberto ou data futura ---
        if not df_abertos.empty or not df_futuros.empty:
            st.markdown("#### ⚠️ Afastamentos em Aberto ou com Data Futura")
            tab_aberto, tab_futuro = st.tabs([f"🔴 Em Aberto ({len(df_abertos)})", f"🟡 Data Futura ({len(df_futuros)})"])

            with tab_aberto:
                if not df_abertos.empty:
                    cols_exibir = [col for col in df_abertos.columns if col not in ['status_afastamento']]
                    st.dataframe(df_abertos[cols_exibir + ['dias_afastamento', 'status_afastamento']
                                            if 'dias_afastamento' in df_abertos.columns else cols_exibir],
                                 use_container_width=True)
                else:
                    st.write("Nenhum afastamento em aberto neste período.")

            with tab_futuro:
                if not df_futuros.empty:
                    cols_exibir = [col for col in df_futuros.columns if col not in ['status_afastamento']]
                    st.dataframe(df_futuros[cols_exibir + ['dias_afastamento', 'status_afastamento']
                                            if 'dias_afastamento' in df_futuros.columns else cols_exibir],
                                 use_container_width=True)
                else:
                    st.write("Nenhum afastamento com data futura neste período.")

        # --- Lista completa de afastados ---
        with st.expander(f"📄 Lista completa de afastados no período{label_emp}"):
            if not df_af_mes.empty:
                st.dataframe(df_af_mes, use_container_width=True)
            else:
                st.write("Sem registros para este período.")

else:
    st.info("⬅️ Importe o BI_RH.xlsx na barra lateral para visualizar os indicadores.")
