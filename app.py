import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Dashboard RH Profissional", layout="wide")


@st.cache_data
def carregar_dados(file):
    try:
        xls = pd.ExcelFile(file)
        lista_abas = xls.sheet_names

        aba_t  = next((s for s in lista_abas if 'turn'  in s.lower()), None)
        aba_a  = next((s for s in lista_abas if 'admit' in s.lower()), None)
        aba_af = next((s for s in lista_abas if s.strip().lower() == 'afastado'), None)

        df_turnover  = pd.read_excel(xls, sheet_name=aba_t)
        df_admitidos = pd.read_excel(xls, sheet_name=aba_a)
        df_af_raw    = pd.read_excel(xls, sheet_name=aba_af) if aba_af else pd.DataFrame()

        for df in [df_turnover, df_admitidos]:
            df.columns = df.columns.str.strip().str.lower()

        if not df_af_raw.empty:
            df_af_raw.columns = df_af_raw.columns.str.strip()

        C_EMP = 'Empresa'
        C_INI = 'Data início'
        C_FIM = 'Data término'
        C_MOT = 'Tipo Afastamento'

        if not df_af_raw.empty:
            df_af_raw[C_INI] = pd.to_datetime(df_af_raw[C_INI], errors='coerce')
            # Trata 00/00/0000, nan, vazio → NaT
            fim_raw = df_af_raw[C_FIM].astype(str).str.strip()
            fim_raw = fim_raw.replace({'00/00/0000': None, 'nan': None, 'NaT': None, '': None})
            df_af_raw[C_FIM] = pd.to_datetime(fim_raw, errors='coerce')

        # --- TURNOVER ---
        col_mes_t = next((c for c in df_turnover.columns if 'mês' in c or 'mes' in c), None)
        df_turnover['mês_ano'] = pd.to_datetime(df_turnover[col_mes_t], errors='coerce')
        df_turnover = df_turnover.dropna(subset=['mês_ano'])
        df_turnover['periodo']  = df_turnover['mês_ano'].dt.to_period('M')
        df_turnover['ano']      = df_turnover['mês_ano'].dt.year.astype(int)
        df_turnover['mes_nome'] = df_turnover['mês_ano'].dt.strftime('%m - %b')

        for c in ['admissões', 'desligamentos', 'colaboradores']:
            if c in df_turnover.columns:
                df_turnover[c] = pd.to_numeric(df_turnover[c], errors='coerce').fillna(0)

        df_turnover['turnover_taxa'] = (
            ((df_turnover['admissões'] + df_turnover['desligamentos']) / 2) /
            df_turnover['colaboradores'].replace(0, 1)
        ) * 100
        df_turnover['retencao_taxa'] = (
            df_turnover['desligamentos'] /
            df_turnover['colaboradores'].replace(0, 1)
        ) * 100

        return df_turnover, df_admitidos, df_af_raw, (C_INI, C_FIM, C_MOT, C_EMP)

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
        return None


def calc_iniciados(df, c_ini, ini_mes, fim_mes):
    """Afastamentos com Data início dentro do mês selecionado."""
    return df[
        df[c_ini].notna() &
        (df[c_ini] >= ini_mes) &
        (df[c_ini] <= fim_mes)
    ].copy()


def calc_total_afastados(df, c_ini, c_fim):
    """
    Total afastados ativos — base HOJE, SEM filtro de Data início:
      • Data término nula / 00/00/0000 (já NaT na carga)
      • Data término > hoje (data real do sistema)
    Retorna: (total_df, nulos_df, futuros_df)
    """
    hoje = pd.Timestamp.today().normalize()
    base    = df[df[c_ini].notna()].copy()
    nulos   = base[base[c_fim].isna()]
    futuros = base[base[c_fim].notna() & (base[c_fim] > hoje)]
    total   = pd.concat([nulos, futuros]).drop_duplicates()
    return total, nulos, futuros


# ─── INTERFACE ────────────────────────────────────────────────────────────────
st.sidebar.header("📁 Importação")
arquivo_subido = st.sidebar.file_uploader("Selecione o BI_RH.xlsx", type=["xlsx"])

if arquivo_subido:
    dados = carregar_dados(arquivo_subido)
    if dados:
        df_t, df_a, df_af, (c_ini, c_fim, c_mot, c_emp) = dados

        # ─── FILTROS TURNOVER ──────────────────────────────────────────────
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Turnover")
        ano_sel  = st.sidebar.selectbox("Ano", sorted(df_t['ano'].unique(), reverse=True))
        df_meses = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')
        mes_sel  = st.sidebar.selectbox("Mês", df_meses['mes_nome'].unique())

        data_sel     = df_meses[df_meses['mes_nome'] == mes_sel]['mês_ano'].iloc[0]
        per_atual    = data_sel.to_period('M')
        per_anterior = (data_sel - pd.DateOffset(months=1)).to_period('M')

        row_atual    = df_t[df_t['periodo'] == per_atual].iloc[0]
        row_ant_list = df_t[df_t['periodo'] == per_anterior]
        row_ant      = row_ant_list.iloc[0] if not row_ant_list.empty else None

        # ─── KPIs TURNOVER ─────────────────────────────────────────────────
        st.title(f"📊 Indicadores RH - {mes_sel}/{ano_sel}")

        def calc_delta(val_atual, col):
            return (val_atual - row_ant[col]) if row_ant is not None else None

        msg_ajuda = "Comparação com o mês anterior."

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

        # ─── GRÁFICO TURNOVER ──────────────────────────────────────────────
        st.subheader("📈 Evolução da Movimentação Mensal")
        df_ano_plot = df_t[df_t['ano'] == ano_sel].sort_values('mês_ano')

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_ano_plot['mes_nome'], y=df_ano_plot['admissões'],
            name='Admissões', marker_color='#2ecc71',
            text=df_ano_plot['admissões'], textposition='outside'
        ))
        fig.add_trace(go.Bar(
            x=df_ano_plot['mes_nome'], y=df_ano_plot['desligamentos'],
            name='Desligamentos', marker_color='#e74c3c',
            text=df_ano_plot['desligamentos'], textposition='outside'
        ))
        fig.add_trace(go.Scatter(
            x=df_ano_plot['mes_nome'], y=df_ano_plot['colaboradores'],
            name='Efetivo Total', yaxis='y2',
            line=dict(color='#3498db', width=4),
            mode='lines+markers+text',
            text=df_ano_plot['colaboradores'].astype(int),
            textposition='top center'
        ))
        fig.update_layout(
            yaxis=dict(title="Volume"),
            yaxis2=dict(title="Efetivo Total", overlaying='y', side='right'),
            barmode='group',
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig, use_container_width=True)

        # ─── AFASTAMENTOS ──────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("🏥 Painel de Afastamentos")

        if not df_af.empty:

            # ── Filtros próprios para Afastamentos (sidebar) ────────────────
            st.sidebar.markdown("---")
            st.sidebar.subheader("🏥 Afastamentos")

            anos_af = sorted(
                df_af[c_ini].dropna().dt.year.unique().astype(int).tolist(),
                reverse=True
            )
            ano_af = st.sidebar.selectbox("Ano (Afastamentos)", anos_af, key="ano_af")

            meses_af = (
                df_af[df_af[c_ini].dt.year == ano_af][c_ini]
                .dropna()
                .dt.to_period('M')
                .drop_duplicates()
                .sort_values()
            )
            opcoes_mes_af = [p.strftime('%m - %b') for p in meses_af]
            mes_af_str = st.sidebar.selectbox("Mês (Afastamentos)", opcoes_mes_af, key="mes_af")

            mes_num_af = int(mes_af_str.split(' - ')[0])
            ini_mes_af = pd.Timestamp(year=ano_af, month=mes_num_af, day=1)
            fim_mes_af = ini_mes_af + pd.offsets.MonthEnd(0)

            todas_empresas = sorted(df_af[c_emp].dropna().unique().tolist())
            emp_sel = st.sidebar.selectbox(
                "🏢 Empresa (Afastamentos)",
                ['Todas'] + todas_empresas,
                key="filtro_empresa"
            )
            base_emp = df_af if emp_sel == 'Todas' else df_af[df_af[c_emp] == emp_sel]

            hoje_label = pd.Timestamp.today().strftime('%d/%m/%Y')

            # ── Cálculos ────────────────────────────────────────────────────
            # KPIs: sempre todas as empresas
            ini_geral                            = calc_iniciados(df_af, c_ini, ini_mes_af, fim_mes_af)
            total_geral, nulos_geral, fut_geral  = calc_total_afastados(df_af, c_ini, c_fim)

            # Delta iniciados (mês anterior)
            ini_ant_af = (ini_mes_af - pd.DateOffset(months=1)).replace(day=1)
            fim_ant_af = ini_ant_af + pd.offsets.MonthEnd(0)
            ini_ant_g  = calc_iniciados(df_af, c_ini, ini_ant_af, fim_ant_af)

            # Gráficos e listas: filtrado por empresa
            ini_emp                         = calc_iniciados(base_emp, c_ini, ini_mes_af, fim_mes_af)
            total_emp, nulos_emp, fut_emp   = calc_total_afastados(base_emp, c_ini, c_fim)

            # ── KPIs ────────────────────────────────────────────────────────
            st.markdown(
                f"**Período: {mes_af_str}/{ano_af}**  |  "
                f"Empresa: **{emp_sel}**  |  "
                f"Referência: **{hoje_label}**"
            )

            k1, k2, k3, k4 = st.columns(4)
            k1.metric(
                "Iniciaram no Mês",
                len(ini_geral),
                delta=int(len(ini_geral) - len(ini_ant_g)),
                delta_color="inverse",
                help=f"Data início em {mes_af_str}/{ano_af} — todas as empresas."
            )
            k2.metric(
                "Total Afastados",
                len(total_geral),
                help=(
                    f"Nulos/00/00/0000 ({len(nulos_geral)}) + "
                    f"Data término > {hoje_label} ({len(fut_geral)}) — toda a base."
                )
            )
            k3.metric(
                "Sem Data (00/00/0000)",
                len(nulos_geral),
                help="Subgrupo: Data término em branco ou 00/00/0000."
            )
            k4.metric(
                "Com Retorno Futuro",
                len(fut_geral),
                help=f"Subgrupo: Data término registrada e posterior a {hoje_label}."
            )

            st.markdown("---")

            # ── Gráfico por Empresa ─────────────────────────────────────────
            st.subheader("🏢 Total de Afastados por Empresa")
            resumo_emp_df = (
                total_geral.groupby(c_emp)
                .size()
                .reset_index(name='Afastados')
                .rename(columns={c_emp: 'Empresa'})
                .sort_values('Afastados', ascending=True)
            )
            resumo_emp_df['cor'] = resumo_emp_df['Empresa'].apply(
                lambda e: '#e74c3c' if (emp_sel != 'Todas' and e == emp_sel) else '#3498db'
            )
            fig_emp = px.bar(
                resumo_emp_df, x='Afastados', y='Empresa', orientation='h',
                text='Afastados', color='cor', color_discrete_map='identity',
            )
            fig_emp.update_traces(textposition='outside', textfont_size=12)
            fig_emp.update_layout(
                height=max(200, len(resumo_emp_df) * 50),
                margin=dict(t=10, b=10, l=10, r=40),
                xaxis_title="Qtd Afastados", yaxis_title="", showlegend=False,
            )
            st.plotly_chart(fig_emp, use_container_width=True)

            st.markdown("---")

            # ── Gráfico Motivos (filtrado por empresa) ──────────────────────
            st.subheader("Motivos de Afastamento")
            if not total_emp.empty:
                resumo_mot = total_emp[c_mot].value_counts().reset_index()
                resumo_mot.columns = ['motivo', 'quantidade']
                fig_mot = px.bar(
                    resumo_mot, x='quantidade', y='motivo', orientation='h',
                    text='quantidade', color_discrete_sequence=['#e67e22']
                )
                fig_mot.update_traces(textposition='outside')
                fig_mot.update_layout(
                    height=max(200, len(resumo_mot) * 45),
                    yaxis_title="", xaxis_title="Qtd"
                )
                st.plotly_chart(fig_mot, use_container_width=True)
            else:
                st.info("Nenhum afastamento ativo encontrado para a empresa selecionada.")

            st.markdown("---")

            # ── Listas Detalhadas ───────────────────────────────────────────
            cols_exibir = [c for c in [c_emp, 'RE', 'Nome', 'Função', c_mot, c_ini, c_fim]
                           if c in df_af.columns]

            with st.expander(
                f"📋 Sem Data de Retorno (nulo / 00/00/0000) — {emp_sel} ({len(nulos_emp)} registros)"
            ):
                st.dataframe(
                    nulos_emp[cols_exibir].sort_values(c_ini),
                    use_container_width=True
                )

            with st.expander(
                f"📋 Com Data de Retorno Futura — {emp_sel} ({len(fut_emp)} registros)"
            ):
                st.caption(f"Data término posterior a hoje ({hoje_label}).")
                st.dataframe(
                    fut_emp[cols_exibir].sort_values(c_fim),
                    use_container_width=True
                )

        else:
            st.warning("⚠️ Aba de afastamentos não encontrada ou vazia.")

else:
    st.info("Importe o BI_RH.xlsx para visualizar os indicadores.")
