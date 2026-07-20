"""Analytics Lab — dashboard Rocket vs. resto de canales.

Convierte los postbacks del MMP (prod_tracking.postbacks_typed) en una lectura
de qué tan bien performa Rocket frente al resto de los canales del cliente.

Data en vivo desde Athena (PyAthena) o desde un CSV export como fallback.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src import athena, metrics, theme
from src.config import list_clients, load_client
from src.queries import q1_weekly_by_channel

st.set_page_config(page_title="Analytics Lab · Rocket Lab", page_icon="📊", layout="wide")
theme.inject_css()


# --------------------------------------------------------------------------- #
# Helpers de formato
# --------------------------------------------------------------------------- #
def money(x) -> str:
    return "—" if pd.isna(x) else f"${x:,.2f}"


def integer(x) -> str:
    return "—" if pd.isna(x) else f"{int(x):,}"


def ratio(x, dec: int = 3) -> str:
    return "—" if pd.isna(x) else f"{x:,.{dec}f}"


def pct(x, dec: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x:+.{dec}f}%"


# --------------------------------------------------------------------------- #
# Sidebar — parámetros
# --------------------------------------------------------------------------- #
clients = list_clients()
with st.sidebar:
    st.markdown("### Parámetros")
    slug = st.selectbox("Cliente", [c[0] for c in clients],
                        format_func=lambda s: dict(clients)[s])
    cfg = load_client(slug)

    app_labels = {a.app_id: f"{a.label} ({a.app_id})" for a in cfg.apps}
    sel_apps = st.multiselect("Apps", cfg.app_ids, default=cfg.app_ids,
                              format_func=lambda a: app_labels[a])

    today = date.today()
    dr = st.date_input("Rango de fechas",
                       value=(today - timedelta(days=90), today),
                       max_value=today)
    start, end = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dr, dr))

    st.markdown("---")
    live_ok = athena.has_credentials()
    source = st.radio(
        "Fuente de datos",
        ["Athena (vivo)", "CSV export"],
        index=0 if live_ok else 1,
        help="Athena requiere credenciales en secrets. Si no hay, usá un CSV.",
    )
    if source == "Athena (vivo)" and not live_ok:
        st.warning("Sin credenciales de Athena configuradas. Cambiá a CSV o "
                   "cargá secrets.toml.", icon="⚠️")

    uploaded = None
    use_sample = False
    if source == "CSV export":
        uploaded = st.file_uploader("CSV (salida de Q1)", type=["csv"])
        use_sample = st.checkbox("Usar datos de muestra (data/sample_vix.csv)",
                                 value=uploaded is None)

    st.markdown("---")
    min_installs = st.number_input(
        "Piso de installs para la mediana del resto", 0, 100_000, 100, step=50,
        help="Canales con menos installs que esto se excluyen del cálculo de "
             "la mediana (evita que canales chicos con 1 compra distorsionen).",
    )


# --------------------------------------------------------------------------- #
# Carga de datos
# --------------------------------------------------------------------------- #
sql = q1_weekly_by_channel(cfg, start, end, sel_apps or cfg.app_ids)


@st.cache_data(ttl=600)
def _load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


def load_data() -> pd.DataFrame | None:
    if source == "Athena (vivo)":
        if not live_ok:
            return None
        try:
            return athena.run_query(sql)
        except Exception as e:  # noqa: BLE001
            st.error(f"Error consultando Athena: {e}")
            return None
    src_file = uploaded
    if src_file is None and use_sample:
        sample = Path(__file__).resolve().parent / "data" / "sample_vix.csv"
        if sample.exists():
            src_file = str(sample)
    if src_file is not None:
        df = _load_csv(src_file)
        if sel_apps:
            df = df[df["app_id"].isin(sel_apps)]
        return df
    return None


df_raw = load_data()

theme.header(
    "Analytics Lab —", cfg.name,
    "Rocket vs. el resto de los canales · postbacks del MMP (modo probabilístico)",
)

if df_raw is None or df_raw.empty:
    if source == "CSV export" and uploaded is None and not use_sample:
        st.info("Cargá un CSV export de la query Q1 en la barra lateral para "
                "empezar, o configurá Athena para datos en vivo.")
    else:
        st.warning("No hay datos para el período/apps seleccionados.")
    with st.expander("Ver query SQL"):
        st.code(sql, language="sql")
    theme.footer(f"{start:%d-%b-%Y} → {end:%d-%b-%Y}")
    st.stop()

df = metrics.normalize(df_raw, cfg)

# --------------------------------------------------------------------------- #
# Sección 1 — Rocket vs. resto (headline)
# --------------------------------------------------------------------------- #
comp = metrics.rocket_vs_rest(df, cfg, min_installs=int(min_installs))
r_tot, rest_tot = comp["_rocket_totals"], comp["_rest_totals"]

wins = sum(1 for m in comp["metrics"].values() if m["mejor"] is True)
evaluables = sum(1 for m in comp["metrics"].values() if m["mejor"] is not None)

st.markdown("#### Rocket vs. resto de canales pagos")
if r_tot["installs"] == 0:
    st.warning("Rocket no tiene installs en este período — no se puede comparar. "
               "Revisá el mapeo de canales de Rocket en la config del cliente.")
else:
    st.markdown(
        f"En este período Rocket queda **mejor que el resto de los canales pagos "
        f"en {wins} de {evaluables}** métricas de calidad. "
        f"El benchmark del *resto* es el pooled de todos los canales pagos "
        f"no-Rocket (excluye orgánico).",
    )
    cols = st.columns(3)
    for col, (key, m) in zip(cols, comp["metrics"].items()):
        fmt = money if key in ("ticket_promedio",) else (
            (lambda v: ratio(v, 4)) if key == "arpi" else (lambda v: ratio(v, 3)))
        if m["mejor"] is None:
            b = theme.badge("s/d", "neutral")
        elif m["mejor"]:
            b = theme.badge(f"▲ {pct(m['delta_pct'])} vs resto", "win")
        else:
            b = theme.badge(f"▼ {pct(m['delta_pct'])} vs resto", "lose")
        cmp_html = (
            f"{b}<br><span style='color:#696A6B'>Resto (pooled): "
            f"{fmt(m['resto_pooled'])} · mediana: {fmt(m['resto_mediana'])}</span>"
        )
        col.markdown(theme.kpi_card(m["label"], fmt(m["rocket"]), cmp_html),
                     unsafe_allow_html=True)

# Totales de contexto
st.markdown("")
c1, c2, c3, c4 = st.columns(4)
tot_rev = df[~df["es_organico"]]["revenue_usd"].sum()
rocket_rev = r_tot["revenue_usd"]
share = (rocket_rev / tot_rev * 100) if tot_rev else np.nan
c1.markdown(theme.kpi_card("Revenue Rocket", money(rocket_rev)), unsafe_allow_html=True)
c2.markdown(theme.kpi_card("Share de revenue Rocket", pct(share).replace("+", "")),
            unsafe_allow_html=True)
c3.markdown(theme.kpi_card("Installs Rocket", integer(r_tot["installs"])), unsafe_allow_html=True)
c4.markdown(theme.kpi_card("Compradores Rocket", integer(r_tot["compradores_unicos"])),
            unsafe_allow_html=True)

st.markdown('<div class="rl-grad-bar"></div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Sección 2 — Comparación por canal
# --------------------------------------------------------------------------- #
st.markdown("#### Por canal")
by_ch = metrics.aggregate_by_channel(df)
metric_opt = st.selectbox(
    "Métrica",
    ["arpi", "ticket_promedio", "tasa_compra", "revenue_usd", "installs", "compradores_unicos"],
    format_func=lambda m: metrics.METRIC_LABELS[m],
)
paid = by_ch[~by_ch["es_organico"]].copy()
topn = paid.nlargest(15, "revenue_usd").sort_values(metric_opt, ascending=True)
topn["color"] = np.where(topn["es_rocket"], "Rocket", "Resto")
fig = px.bar(
    topn, x=metric_opt, y="canal", orientation="h",
    color="color", color_discrete_map={"Rocket": theme.VIOLET, "Resto": theme.GRAY_DK},
    labels={metric_opt: metrics.METRIC_LABELS[metric_opt], "canal": "", "color": ""},
)
fig.update_layout(height=460, plot_bgcolor="white", paper_bgcolor="white",
                  font_family="Inter", margin=dict(l=10, r=10, t=10, b=10),
                  legend=dict(orientation="h", y=1.08))
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------- #
# Sección 3 — Evolución semanal
# --------------------------------------------------------------------------- #
if "semana" in df.columns and df["semana"].notna().any():
    st.markdown("#### Evolución semanal — Rocket vs. resto")
    ev_metric = st.selectbox(
        "Métrica temporal", ["revenue_usd", "installs", "compradores_unicos"],
        format_func=lambda m: metrics.METRIC_LABELS[m], key="ev",
    )
    tmp = df[~df["es_organico"]].copy()
    tmp["segmento"] = np.where(tmp["es_rocket"], "Rocket", "Resto pagos")
    ev = tmp.groupby(["semana", "segmento"], as_index=False)[ev_metric].sum()
    figl = px.line(
        ev, x="semana", y=ev_metric, color="segmento", markers=True,
        color_discrete_map={"Rocket": theme.VIOLET, "Resto pagos": theme.BLUE},
        labels={ev_metric: metrics.METRIC_LABELS[ev_metric], "semana": "", "segmento": ""},
    )
    figl.update_layout(height=380, plot_bgcolor="white", paper_bgcolor="white",
                       font_family="Inter", margin=dict(l=10, r=10, t=10, b=10),
                       legend=dict(orientation="h", y=1.12))
    st.plotly_chart(figl, use_container_width=True)

# --------------------------------------------------------------------------- #
# Sección 4 — Tabla + query
# --------------------------------------------------------------------------- #
st.markdown("#### Detalle por canal")
show = by_ch[["canal", "grupo", "installs", "compradores_unicos", "total_compras",
              "revenue_usd", "arpi", "ticket_promedio", "tasa_compra"]].copy()
st.dataframe(
    show,
    use_container_width=True, hide_index=True,
    column_config={
        "revenue_usd": st.column_config.NumberColumn("revenue_usd", format="$%.2f"),
        "arpi": st.column_config.NumberColumn("arpi", format="%.4f"),
        "ticket_promedio": st.column_config.NumberColumn("ticket_promedio", format="$%.2f"),
        "tasa_compra": st.column_config.NumberColumn("tasa_compra", format="%.4f"),
    },
)

with st.expander("Ver query SQL ejecutada"):
    st.code(sql, language="sql")

csv_out = show.to_csv(index=False).encode("utf-8")
st.download_button("Descargar tabla (CSV)", csv_out,
                   file_name=f"analytics_lab_{slug}_{start}_{end}.csv", mime="text/csv")

theme.footer(f"{start:%d-%b-%Y} → {end:%d-%b-%Y}")
