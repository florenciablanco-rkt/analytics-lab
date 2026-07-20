"""Analytics Lab — dashboard Rocket vs. resto de canales (cliente Vix).

Convierte los postbacks del MMP en una lectura de qué tan bien performa Rocket
frente al resto de los canales. Fuente: Athena en vivo si hay credenciales,
si no el Google Sheet (vivo o snapshot). Sin subida manual de archivos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src import datasource, metrics, theme
from src.config import load_client

st.set_page_config(page_title="Analytics Lab · Rocket Lab", page_icon="📊", layout="wide")
theme.inject_css()

CLIENT = "vix"          # cliente fijo por ahora
cfg = load_client(CLIENT)


# --------------------------------------------------------------------------- #
# Formato
# --------------------------------------------------------------------------- #
def money(x) -> str:
    return "—" if pd.isna(x) else f"${x:,.2f}"


def integer(x) -> str:
    return "—" if pd.isna(x) else f"{int(x):,}"


def ratio(x, dec: int = 3) -> str:
    return "—" if pd.isna(x) else f"{x:,.{dec}f}"


def pct(x, dec: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x:+.{dec}f}%"


def fmt_metric(key: str):
    if key == "ticket_promedio":
        return money
    if key in ("revenue_usd",):
        return money
    if key == "arpi":
        return lambda v: ratio(v, 4)
    if key in ("installs", "compradores_unicos", "total_compras"):
        return integer
    return lambda v: ratio(v, 3)


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
df_raw, source_label, live = datasource.get_data(cfg)

theme.header(
    "Analytics Lab —", cfg.name,
    "Rocket vs. el resto de los canales · postbacks del MMP (modo probabilístico)",
)

if df_raw.empty:
    st.warning("No hay datos disponibles para este cliente.")
    theme.footer("")
    st.stop()

df_all = metrics.normalize(df_raw, cfg)
weeks = sorted({pd.Timestamp(w).date() for w in df_all["semana"].dropna().unique()})

# --------------------------------------------------------------------------- #
# Sidebar — filtro de fecha (dos modos)
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### Filtro de fecha")
    mode = st.radio("Modo", ["Rango de fechas", "Semanas (deslizable)"])
    if mode == "Rango de fechas":
        dr = st.date_input("Rango", value=(weeks[0], weeks[-1]),
                           min_value=weeks[0], max_value=weeks[-1])
        start, end = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dr, dr))
    else:
        if len(weeks) > 1:
            start, end = st.select_slider(
                "Semanas", options=weeks, value=(weeks[0], weeks[-1]),
                format_func=lambda d: d.strftime("%d-%b-%y"))
        else:
            start = end = weeks[0]
            st.caption(f"Única semana disponible: {weeks[0]:%d-%b-%y}")

    st.markdown("---")
    tag = "🟢 en vivo" if live else "🟡 snapshot"
    st.caption(f"Fuente: **{source_label}** {tag}")
    st.caption(f"Datos disponibles: {weeks[0]:%d-%b-%Y} → {weeks[-1]:%d-%b-%Y}")

mask = (df_all["semana"].dt.date >= start) & (df_all["semana"].dt.date <= end)
df = df_all[mask]
if df.empty:
    st.warning("No hay datos en el período seleccionado.")
    theme.footer(f"{start:%d-%b-%Y} → {end:%d-%b-%Y}")
    st.stop()

# --------------------------------------------------------------------------- #
# Sección 1 — Rocket vs. resto (headline)
# --------------------------------------------------------------------------- #
comp = metrics.rocket_vs_rest(df, cfg)
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
        f"en {wins} de {evaluables}** métricas de calidad. El *resto* es el "
        f"promedio ponderado de todos los canales pagos no-Rocket (excluye orgánico).")
    cols = st.columns(3)
    for col, (key, m) in zip(cols, comp["metrics"].items()):
        f = fmt_metric(key)
        if m["mejor"] is None:
            b = theme.badge("s/d", "neutral")
        elif m["mejor"]:
            b = theme.badge(f"▲ {pct(m['delta_pct'])} vs resto", "win")
        else:
            b = theme.badge(f"▼ {pct(m['delta_pct'])} vs resto", "lose")
        cmp_html = (f"{b}<br><span style='color:#696A6B'>Resto: {f(m['resto'])}</span>")
        col.markdown(theme.kpi_card(m["label"], f(m["rocket"]), cmp_html),
                     unsafe_allow_html=True)

st.markdown("")
c1, c2, c3, c4 = st.columns(4)
tot_rev = df[~df["es_organico"]]["revenue_usd"].sum()
share = (r_tot["revenue_usd"] / tot_rev * 100) if tot_rev else np.nan
c1.markdown(theme.kpi_card("Revenue Rocket", money(r_tot["revenue_usd"])), unsafe_allow_html=True)
c2.markdown(theme.kpi_card("Share de revenue Rocket", pct(share).replace("+", "")),
            unsafe_allow_html=True)
c3.markdown(theme.kpi_card("Installs Rocket", integer(r_tot["installs"])), unsafe_allow_html=True)
c4.markdown(theme.kpi_card("Compradores Rocket", integer(r_tot["compradores_unicos"])),
            unsafe_allow_html=True)

st.markdown('<div class="rl-grad-bar"></div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Sección 2 — Ranking por canal (colorido)
# --------------------------------------------------------------------------- #
st.markdown("#### Ranking por canal")
by_ch = metrics.aggregate_by_channel(df)
metric_opt = st.selectbox(
    "Métrica", ["revenue_usd", "arpi", "ticket_promedio", "tasa_compra",
                "installs", "compradores_unicos"],
    format_func=lambda m: metrics.METRIC_LABELS[m])
paid = by_ch[~by_ch["es_organico"]].copy()
topn = paid.nlargest(15, "revenue_usd").sort_values(metric_opt, ascending=True)
fig = px.bar(
    topn, x=metric_opt, y="canal", orientation="h", color="canal",
    color_discrete_sequence=theme.CHANNEL_PALETTE * 2,
    labels={metric_opt: metrics.METRIC_LABELS[metric_opt], "canal": ""})
fig.update_layout(height=470, plot_bgcolor="white", paper_bgcolor="white",
                  font_family="Inter", showlegend=False,
                  margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------- #
# Sección 3 — Mix de revenue por canal (área apilada, colorido)
# --------------------------------------------------------------------------- #
if len(weeks) > 1 and df["semana"].notna().any():
    st.markdown("#### Evolución semanal por canal")
    ev_metric = st.selectbox(
        "Métrica temporal", ["revenue_usd", "installs", "compradores_unicos"],
        format_func=lambda m: metrics.METRIC_LABELS[m], key="ev")

    paid_df = df[~df["es_organico"]].copy()
    top_channels = (paid_df.groupby("canal")["revenue_usd"].sum()
                    .nlargest(8).index.tolist())
    paid_df["canal_top"] = np.where(paid_df["canal"].isin(top_channels),
                                    paid_df["canal"], "Otros")
    ev = paid_df.groupby(["semana", "canal_top"], as_index=False)[ev_metric].sum()

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Área apilada (composición)")
        fig_a = px.area(
            ev, x="semana", y=ev_metric, color="canal_top",
            color_discrete_sequence=theme.CHANNEL_PALETTE,
            labels={ev_metric: metrics.METRIC_LABELS[ev_metric], "semana": "", "canal_top": ""})
        fig_a.update_layout(height=360, plot_bgcolor="white", paper_bgcolor="white",
                            font_family="Inter", margin=dict(l=10, r=10, t=10, b=10),
                            legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_a, use_container_width=True)
    with col_b:
        st.caption("Líneas por canal")
        fig_b = px.line(
            ev, x="semana", y=ev_metric, color="canal_top", markers=True,
            color_discrete_sequence=theme.CHANNEL_PALETTE,
            labels={ev_metric: metrics.METRIC_LABELS[ev_metric], "semana": "", "canal_top": ""})
        fig_b.update_layout(height=360, plot_bgcolor="white", paper_bgcolor="white",
                            font_family="Inter", margin=dict(l=10, r=10, t=10, b=10),
                            legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_b, use_container_width=True)

# --------------------------------------------------------------------------- #
# Sección 4 — Tabla + export
# --------------------------------------------------------------------------- #
st.markdown("#### Detalle por canal")
show = by_ch[["canal", "grupo", "installs", "compradores_unicos", "total_compras",
              "revenue_usd", "arpi", "ticket_promedio", "tasa_compra"]].copy()
st.dataframe(
    show, use_container_width=True, hide_index=True,
    column_config={
        "revenue_usd": st.column_config.NumberColumn("revenue_usd", format="$%.2f"),
        "arpi": st.column_config.NumberColumn("arpi", format="%.4f"),
        "ticket_promedio": st.column_config.NumberColumn("ticket_promedio", format="$%.2f"),
        "tasa_compra": st.column_config.NumberColumn("tasa_compra", format="%.4f"),
    })
st.download_button("Descargar tabla (CSV)", show.to_csv(index=False).encode("utf-8"),
                   file_name=f"analytics_lab_vix_{start}_{end}.csv", mime="text/csv")

theme.footer(f"{start:%d-%b-%Y} → {end:%d-%b-%Y}")
