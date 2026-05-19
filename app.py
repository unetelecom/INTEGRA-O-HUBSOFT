"""
Dashboard Hubsoft — app.py
Execute com:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time

from hubsoft_api import HubsoftAPI

# ──────────────────────────────────────────────
# Configuração da página
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="JetTelecom · Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CSS customizado
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

:root {
    --jet:    #0a0f1e;
    --panel:  #111827;
    --border: #1e2d40;
    --accent: #00e5ff;
    --green:  #00ffa3;
    --red:    #ff4d6d;
    --yellow: #ffd166;
    --text:   #e2e8f0;
    --muted:  #64748b;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--jet) !important;
    color: var(--text) !important;
    font-family: 'Syne', sans-serif !important;
}

[data-testid="stSidebar"] {
    background-color: var(--panel) !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * { color: var(--text) !important; }

h1, h2, h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }

/* Métricas */
[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.2rem !important;
}
[data-testid="stMetricLabel"]  { color: var(--muted) !important; font-size: .75rem !important; text-transform: uppercase; letter-spacing: .08em; }
[data-testid="stMetricValue"]  { color: var(--accent) !important; font-family: 'Space Mono', monospace !important; font-size: 1.8rem !important; }
[data-testid="stMetricDelta"]  { font-size: .8rem !important; }

/* Botões */
.stButton > button {
    background: transparent !important;
    border: 1px solid var(--accent) !important;
    color: var(--accent) !important;
    border-radius: 8px !important;
    font-family: 'Space Mono', monospace !important;
    font-size: .8rem !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    background: var(--accent) !important;
    color: var(--jet) !important;
}

/* Selectbox / multiselect */
.stSelectbox > div > div, .stMultiSelect > div > div {
    background: var(--panel) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}

/* Tabs */
[data-baseweb="tab-list"] { background: var(--panel) !important; border-radius: 10px; gap: 4px; }
[data-baseweb="tab"] { color: var(--muted) !important; border-radius: 8px !important; font-family:'Syne',sans-serif !important; }
[aria-selected="true"][data-baseweb="tab"] { background: var(--border) !important; color: var(--accent) !important; }

/* Tabelas */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 10px; }

/* Divider */
hr { border-color: var(--border) !important; }

/* Status badges */
.badge {
    display:inline-block; padding:2px 10px;
    border-radius: 99px; font-size:.7rem;
    font-family:'Space Mono',monospace; font-weight:700;
}
.badge-green  { background:#00ffa320; color:#00ffa3; border:1px solid #00ffa340; }
.badge-red    { background:#ff4d6d20; color:#ff4d6d; border:1px solid #ff4d6d40; }
.badge-yellow { background:#ffd16620; color:#ffd166; border:1px solid #ffd16640; }
.badge-blue   { background:#00e5ff20; color:#00e5ff; border:1px solid #00e5ff40; }

/* Card container */
.kpi-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.4rem;
    margin-bottom: .5rem;
}
.kpi-title { color: var(--muted); font-size:.7rem; text-transform:uppercase; letter-spacing:.1em; margin-bottom:.4rem; }
.kpi-value { color: var(--accent); font-family:'Space Mono',monospace; font-size:2rem; font-weight:700; }
.kpi-sub   { color: var(--muted); font-size:.75rem; margin-top:.2rem; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Helpers de gráfico (tema escuro)
# ──────────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0", family="Syne"),
    margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor="#1e2d40", zerolinecolor="#1e2d40"),
    yaxis=dict(gridcolor="#1e2d40", zerolinecolor="#1e2d40"),
)
COLORS = ["#00e5ff", "#00ffa3", "#ffd166", "#ff4d6d", "#c084fc", "#fb923c"]


def styled_fig(fig):
    fig.update_layout(**PLOT_LAYOUT)
    return fig


# ──────────────────────────────────────────────
# Cache e carregamento de dados
# ──────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_api():
    api = HubsoftAPI()
    api.discover()   # introspection: descobre nomes reais dos recursos
    return api


def safe_load(fn, *args, **kwargs):
    """Executa fn com args; retorna (DataFrame, None) ou (DataFrame vazio, msg_erro)."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return pd.DataFrame(), str(e)


@st.cache_data(ttl=300, show_spinner=False)
def load_clientes(_api):
    return safe_load(_api.get_clientes)

@st.cache_data(ttl=300, show_spinner=False)
def load_contratos(_api):
    return safe_load(_api.get_contratos)

@st.cache_data(ttl=300, show_spinner=False)
def load_cobrancas(_api, de, ate):
    return safe_load(_api.get_cobrancas, de, ate)

@st.cache_data(ttl=300, show_spinner=False)
def load_os(_api, de, ate):
    return safe_load(_api.get_ordens_servico, de, ate)


def invalidar_cache():
    load_clientes.clear()
    load_contratos.clear()
    load_cobrancas.clear()
    load_os.clear()


# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📡 JetTelecom")
    st.markdown("**Dashboard Operacional**")
    st.divider()

    st.markdown("### 📅 Período")
    hoje = datetime.today()
    data_ini = st.date_input("De", hoje - timedelta(days=30))
    data_fim = st.date_input("Até", hoje)

    st.divider()
    st.markdown("### 🔄 Atualização")
    auto_refresh = st.toggle("Auto-refresh (5 min)", value=False)
    if st.button("↺  Atualizar agora"):
        invalidar_cache()
        st.rerun()

    st.divider()
    st.markdown(
        f"<span style='color:#64748b;font-size:.7rem'>Última atualização<br>"
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</span>",
        unsafe_allow_html=True,
    )

# auto-refresh
if auto_refresh:
    time.sleep(300)
    invalidar_cache()
    st.rerun()

# ──────────────────────────────────────────────
# Carrega dados
# ──────────────────────────────────────────────
api = get_api()
de_str  = data_ini.strftime("%Y-%m-%d")
ate_str = data_fim.strftime("%Y-%m-%d")

with st.spinner("Conectando à API Hubsoft…"):
    df_cli,  err_cli  = load_clientes(api)
    df_con,  err_con  = load_contratos(api)
    df_cob,  err_cob  = load_cobrancas(api, de_str, ate_str)
    df_os,   err_os   = load_os(api, de_str, ate_str)

# Mostra banner de aviso se algum recurso falhou (sem travar o app)
erros = [(n, e) for n, e in [("Clientes", err_cli), ("Contratos", err_con),
                               ("Cobranças", err_cob), ("OS", err_os)] if e]
if erros:
    with st.expander(f"⚠️ {len(erros)} recurso(s) com erro — clique para ver detalhes"):
        for nome, msg in erros:
            st.error(f"**{nome}:** {msg}")
        st.info("Use a aba 🔬 Diagnóstico para ver os recursos disponíveis no seu schema.")

# ──────────────────────────────────────────────
# Header principal
# ──────────────────────────────────────────────
st.markdown(
    "<h1 style='margin-bottom:.1rem'>📡 Dashboard JetTelecom</h1>"
    "<p style='color:#64748b;margin-top:0'>Visão operacional em tempo real · Hubsoft ERP</p>",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# KPIs globais
# ──────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)

total_cli    = len(df_cli)
ativos       = len(df_cli[df_cli["status"].str.lower() == "ativo"]) if "status" in df_cli.columns else "—"
total_con    = len(df_con)
receita      = df_cob["valor"].sum() if "valor" in df_cob.columns else 0
inadimplente = len(df_cob[df_cob.get("status_pagamento", pd.Series(dtype=str)).str.lower().isin(["pendente","vencido","em_aberto"])]) if "status_pagamento" in df_cob.columns else "—"

k1.metric("👥 Clientes", f"{total_cli:,}")
k2.metric("✅ Ativos", f"{ativos:,}" if isinstance(ativos, int) else ativos)
k3.metric("📄 Contratos", f"{total_con:,}")
k4.metric("💰 Receita (período)", f"R$ {receita:,.2f}")
k5.metric("⚠️ Cobranças abertas", f"{inadimplente}" if isinstance(inadimplente, int) else inadimplente)

st.divider()

# ──────────────────────────────────────────────
# Abas
# ──────────────────────────────────────────────
tab_fin, tab_cli, tab_con, tab_os, tab_diag = st.tabs([
    "💰  Financeiro",
    "👥  Clientes",
    "📄  Contratos",
    "🔧  Ordens de Serviço",
    "🔬  Diagnóstico API",
])


# ════════════════════════════════════════════════
# ABA FINANCEIRO
# ════════════════════════════════════════════════
with tab_fin:
    st.markdown("### Financeiro · Cobranças")

    if df_cob.empty:
        st.info("Nenhuma cobrança encontrada no período selecionado.")
    else:
        # KPIs financeiros
        f1, f2, f3, f4 = st.columns(4)

        if "valor" in df_cob.columns:
            df_cob["valor"] = pd.to_numeric(df_cob["valor"], errors="coerce").fillna(0)

        pago   = df_cob[df_cob.get("status_pagamento", pd.Series(dtype=str)).str.lower() == "pago"]["valor"].sum() if "status_pagamento" in df_cob.columns else 0
        aberto = df_cob[~(df_cob.get("status_pagamento", pd.Series(dtype=str)).str.lower() == "pago")]["valor"].sum() if "status_pagamento" in df_cob.columns else 0
        tx_rec = (pago / (pago + aberto) * 100) if (pago + aberto) > 0 else 0

        f1.metric("Total cobrado",    f"R$ {df_cob['valor'].sum():,.2f}" if 'valor' in df_cob.columns else "—")
        f2.metric("Total recebido",   f"R$ {pago:,.2f}")
        f3.metric("Em aberto",        f"R$ {aberto:,.2f}", delta=f"-{aberto:,.0f}", delta_color="inverse")
        f4.metric("Taxa de recebimento", f"{tx_rec:.1f}%")

        col_g1, col_g2 = st.columns(2)

        # Gráfico: receita por dia
        with col_g1:
            if "data_pagamento" in df_cob.columns and "valor" in df_cob.columns:
                df_pago = df_cob[df_cob.get("status_pagamento", pd.Series(dtype=str)).str.lower() == "pago"].copy()
                df_pago["data_pagamento"] = pd.to_datetime(df_pago["data_pagamento"], errors="coerce")
                df_dia = df_pago.groupby(df_pago["data_pagamento"].dt.date)["valor"].sum().reset_index()
                df_dia.columns = ["data", "valor"]

                fig = px.area(
                    df_dia, x="data", y="valor",
                    title="Receita recebida por dia",
                    color_discrete_sequence=["#00e5ff"],
                )
                fig.update_traces(fill="tozeroy", fillcolor="rgba(0,229,255,.12)")
                st.plotly_chart(styled_fig(fig), use_container_width=True)
            else:
                st.info("Campo data_pagamento não disponível.")

        # Gráfico: status das cobranças
        with col_g2:
            if "status_pagamento" in df_cob.columns:
                dist = df_cob["status_pagamento"].value_counts().reset_index()
                dist.columns = ["status", "qtd"]
                fig2 = px.pie(
                    dist, names="status", values="qtd",
                    title="Distribuição por status",
                    color_discrete_sequence=COLORS,
                    hole=.55,
                )
                st.plotly_chart(styled_fig(fig2), use_container_width=True)

        # Tabela de cobranças
        st.markdown("#### Detalhamento das cobranças")
        colunas_exibir = [c for c in ["id_cobranca","id_cliente","valor","vencimento","status_pagamento","data_pagamento"] if c in df_cob.columns]
        st.dataframe(
            df_cob[colunas_exibir].sort_values("vencimento", ascending=False) if "vencimento" in df_cob.columns else df_cob[colunas_exibir],
            use_container_width=True,
            hide_index=True,
        )


# ════════════════════════════════════════════════
# ABA CLIENTES
# ════════════════════════════════════════════════
with tab_cli:
    st.markdown("### Clientes")

    if df_cli.empty:
        st.info("Nenhum cliente encontrado.")
    else:
        c1, c2 = st.columns(2)

        # Status dos clientes
        with c1:
            if "status" in df_cli.columns:
                dist_status = df_cli["status"].value_counts().reset_index()
                dist_status.columns = ["status", "qtd"]
                fig = px.bar(
                    dist_status, x="status", y="qtd",
                    title="Clientes por status",
                    color="status",
                    color_discrete_sequence=COLORS,
                )
                st.plotly_chart(styled_fig(fig), use_container_width=True)

        # Clientes novos por mês
        with c2:
            data_col = next((c for c in ["data_cadastro","created_at","data_criacao"] if c in df_cli.columns), None)
            if data_col:
                df_cli[data_col] = pd.to_datetime(df_cli[data_col], errors="coerce")
                df_mes = df_cli.groupby(df_cli[data_col].dt.to_period("M")).size().reset_index(name="qtd")
                df_mes[data_col] = df_mes[data_col].astype(str)
                fig2 = px.bar(
                    df_mes.tail(12), x=data_col, y="qtd",
                    title="Novos clientes por mês (últimos 12)",
                    color_discrete_sequence=["#00ffa3"],
                )
                st.plotly_chart(styled_fig(fig2), use_container_width=True)
            else:
                st.info("Campo de data de cadastro não disponível.")

        # Filtro de busca
        st.markdown("#### Tabela de clientes")
        busca = st.text_input("🔍 Buscar cliente (nome, CPF/CNPJ)", placeholder="Digite para filtrar…")
        colunas_cli = [c for c in ["id_cliente","codigo_cliente","nome_razaosocial","cpf_cnpj","email","telefone","status"] if c in df_cli.columns]
        df_view = df_cli[colunas_cli]
        if busca:
            mask = df_view.apply(lambda col: col.astype(str).str.contains(busca, case=False, na=False)).any(axis=1)
            df_view = df_view[mask]

        st.dataframe(df_view, use_container_width=True, hide_index=True)
        st.caption(f"{len(df_view):,} clientes exibidos de {len(df_cli):,} total")


# ════════════════════════════════════════════════
# ABA CONTRATOS
# ════════════════════════════════════════════════
with tab_con:
    st.markdown("### Contratos")

    if df_con.empty:
        st.info("Nenhum contrato encontrado.")
    else:
        ct1, ct2, ct3 = st.columns(3)

        total_ativos_con = len(df_con[df_con["status"].str.lower() == "ativo"]) if "status" in df_con.columns else "—"
        valor_mrr = df_con[df_con.get("status", pd.Series(dtype=str)).str.lower() == "ativo"]["valor"].sum() if "valor" in df_con.columns else 0

        ct1.metric("Total de contratos", f"{len(df_con):,}")
        ct2.metric("Contratos ativos",   f"{total_ativos_con:,}" if isinstance(total_ativos_con, int) else total_ativos_con)
        ct3.metric("MRR estimado",       f"R$ {valor_mrr:,.2f}")

        col_p1, col_p2 = st.columns(2)

        with col_p1:
            if "plano" in df_con.columns:
                dist_plano = df_con["plano"].value_counts().reset_index()
                dist_plano.columns = ["plano", "qtd"]
                fig = px.bar(
                    dist_plano.head(15), x="qtd", y="plano",
                    orientation="h",
                    title="Contratos por plano (Top 15)",
                    color_discrete_sequence=["#c084fc"],
                )
                st.plotly_chart(styled_fig(fig), use_container_width=True)

        with col_p2:
            if "status" in df_con.columns:
                dist_st = df_con["status"].value_counts().reset_index()
                dist_st.columns = ["status", "qtd"]
                fig2 = px.pie(
                    dist_st, names="status", values="qtd",
                    title="Contratos por status",
                    color_discrete_sequence=COLORS,
                    hole=.5,
                )
                st.plotly_chart(styled_fig(fig2), use_container_width=True)

        st.markdown("#### Tabela de contratos")
        colunas_con = [c for c in ["id_contrato","id_cliente","plano","status","valor","data_ativacao"] if c in df_con.columns]
        st.dataframe(df_con[colunas_con], use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════
# ABA ORDENS DE SERVIÇO
# ════════════════════════════════════════════════
with tab_os:
    st.markdown("### Ordens de Serviço")

    if df_os.empty:
        st.info("Nenhuma OS encontrada no período selecionado.")
    else:
        o1, o2, o3, o4 = st.columns(4)

        abertas   = len(df_os[df_os.get("status", pd.Series(dtype=str)).str.lower().isin(["aberta","em_aberto","aberto"])]) if "status" in df_os.columns else "—"
        concluidas= len(df_os[df_os.get("status", pd.Series(dtype=str)).str.lower().isin(["concluida","concluido","finalizada"])]) if "status" in df_os.columns else "—"
        pendentes = len(df_os[df_os.get("status", pd.Series(dtype=str)).str.lower().isin(["pendente","agendada"])]) if "status" in df_os.columns else "—"

        o1.metric("Total OS",   f"{len(df_os):,}")
        o2.metric("Abertas",    f"{abertas}"    if isinstance(abertas,    int) else abertas)
        o3.metric("Concluídas", f"{concluidas}" if isinstance(concluidas, int) else concluidas)
        o4.metric("Pendentes",  f"{pendentes}"  if isinstance(pendentes,  int) else pendentes)

        os1, os2 = st.columns(2)

        with os1:
            if "status" in df_os.columns:
                dist_os = df_os["status"].value_counts().reset_index()
                dist_os.columns = ["status", "qtd"]
                fig = px.bar(
                    dist_os, x="status", y="qtd",
                    title="OS por status",
                    color="status",
                    color_discrete_sequence=COLORS,
                )
                st.plotly_chart(styled_fig(fig), use_container_width=True)

        with os2:
            data_os_col = next((c for c in ["data_abertura","created_at","data_criacao"] if c in df_os.columns), None)
            if data_os_col:
                df_os[data_os_col] = pd.to_datetime(df_os[data_os_col], errors="coerce")
                df_os_dia = df_os.groupby(df_os[data_os_col].dt.date).size().reset_index(name="qtd")
                df_os_dia.columns = ["data", "qtd"]
                fig2 = px.line(
                    df_os_dia, x="data", y="qtd",
                    title="OS abertas por dia",
                    color_discrete_sequence=["#ffd166"],
                    markers=True,
                )
                st.plotly_chart(styled_fig(fig2), use_container_width=True)

        if "tipo" in df_os.columns:
            fig3 = px.pie(
                df_os["tipo"].value_counts().reset_index().rename(columns={"tipo":"tipo","count":"qtd"}),
                names="tipo", values="qtd",
                title="OS por tipo",
                color_discrete_sequence=COLORS,
                hole=.5,
            )
            st.plotly_chart(styled_fig(fig3), use_container_width=True)

        st.markdown("#### Tabela de OS")
        colunas_os = [c for c in ["id_os","id_cliente","tipo","status","descricao","data_abertura","data_conclusao"] if c in df_os.columns]
        busca_os = st.text_input("🔍 Filtrar OS", placeholder="Status, tipo, cliente…", key="busca_os")
        df_os_view = df_os[colunas_os]
        if busca_os:
            mask = df_os_view.apply(lambda col: col.astype(str).str.contains(busca_os, case=False, na=False)).any(axis=1)
            df_os_view = df_os_view[mask]
        st.dataframe(df_os_view, use_container_width=True, hide_index=True)
        st.caption(f"{len(df_os_view):,} OS exibidas de {len(df_os):,} total")

# ════════════════════════════════════════════════
# ABA DIAGNÓSTICO
# ════════════════════════════════════════════════
with tab_diag:
    st.markdown("### 🔬 Diagnóstico da API GraphQL")

    # Mapeamento atual
    st.markdown("#### Mapeamento automático de recursos")
    if api.resource_map:
        for cat, real in api.resource_map.items():
            st.success(f"✅ **{cat}** → `{real}`")
    else:
        st.warning("Nenhum recurso mapeado ainda.")

    not_found = [c for c in ["clientes","contratos","cobrancas","os"]
                 if c not in api.resource_map]
    if not_found:
        st.error(f"❌ Recursos **não encontrados** no schema: {', '.join(not_found)}")

    st.divider()

    # Todos os campos disponíveis
    st.markdown("#### Todos os recursos disponíveis no schema")
    if api.query_fields:
        cols = st.columns(3)
        for i, f in enumerate(sorted(api.query_fields)):
            cols[i % 3].markdown(f"- `{f}`")
    else:
        if st.button("▶ Carregar campos do schema"):
            with st.spinner("Consultando schema…"):
                try:
                    api.discover()
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.divider()

    # Query manual
    st.markdown("#### Query GraphQL manual")
    query_input = st.text_area(
        "Query GraphQL",
        value='{\n  __type(name: "Query") {\n    fields { name }\n  }\n}',
        height=130,
    )
    if st.button("▶ Executar"):
        with st.spinner("Executando…"):
            try:
                result = api._gql(query_input)
                st.json(result)
            except Exception as e:
                st.error(str(e))


# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center;color:#1e2d40;font-size:.7rem'>"
    "JetTelecom · Dashboard Hubsoft · Dados em tempo real via API GraphQL"
    "</p>",
    unsafe_allow_html=True,
)
