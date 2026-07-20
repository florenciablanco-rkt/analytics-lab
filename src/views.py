"""Vistas del dashboard para Q2..Q6. Cada una lee su tab del Sheet (o Athena)
vía datasource.get_query y renderiza. Estado vacío si todavía no hay data.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from . import datasource, theme
from .config import ClientConfig
from .util import coerce_numeric, integer, money

LABELS = {
    "revenue_usd": "Revenue (USD)", "installs": "Installs", "devices": "Devices",
    "compradores": "Compradores", "compradores_unicos": "Compradores únicos",
    "compradores_repetidores": "Repetidores", "tasa_repeticion_pct": "Tasa de repetición (%)",
    "ltv_promedio": "LTV promedio", "ltv_por_install": "LTV por install",
    "revenue_30d": "Revenue 30d", "revenue_60d": "Revenue 60d", "revenue_total": "Revenue total",
}
PLOT = dict(plot_bgcolor="white", paper_bgcolor="white", font_family="Inter",
            margin=dict(l=10, r=10, t=10, b=10))


def _source_caption(label: str, live: bool) -> None:
    tag = "🟢 en vivo" if live else ("🟡 snapshot" if label != "sin datos" else "")
    st.caption(f"Fuente: **{label}** {tag}")


def _empty(sql_file: str, tab: str) -> None:
    st.info("Todavía no hay datos para esta vista.")


def _filter_dates(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if "dt" in df.columns:
        d = pd.to_datetime(df["dt"].astype(str).str[:10], errors="coerce").dt.date
    elif "semana" in df.columns:
        d = pd.to_datetime(df["semana"], errors="coerce").dt.date
    elif "mes" in df.columns:
        m = df["mes"].astype(str)
        return df[(m >= f"{start:%Y-%m}") & (m <= f"{end:%Y-%m}")]
    elif "cohorte_mes" in df.columns:
        m = df["cohorte_mes"].astype(str)
        return df[(m >= f"{start:%Y-%m}") & (m <= f"{end:%Y-%m}")]
    else:
        return df
    return df[(d >= start) & (d <= end)]


def _rocket_mask(cfg: ClientConfig, s: pd.Series) -> pd.Series:
    return s.isin(cfg.rocket_channels)


# --------------------------------------------------------------------------- #
# Q2 — Mix UA vs RTG
# --------------------------------------------------------------------------- #
def render_q2(cfg: ClientConfig, start: date, end: date) -> None:
    df, label, live = datasource.get_query(cfg, "q2", start, end)
    _source_caption(label, live)
    if df.empty:
        _empty("q2_mix_ua_rtg_por_canal_por_dia.sql", "Q2 - Mix UA vs RTG"); return
    df = coerce_numeric(df, ["devices", "compradores", "revenue_usd"])
    df = _filter_dates(df, start, end)
    if df.empty:
        st.warning("Sin datos en el período."); return

    truthy = {"1", "true", "t", "yes", "si", "sí", "1.0"}
    df["tipo"] = np.where(df["is_retargeting"].astype(str).str.strip().str.lower().isin(truthy),
                          "RTG", "UA")
    metric = st.selectbox("Métrica", ["revenue_usd", "devices", "compradores"],
                          format_func=lambda m: LABELS[m], key="q2m")

    overall = df.groupby("tipo", as_index=False)[metric].sum()
    tot = overall[metric].sum()
    c1, c2 = st.columns(2)
    for col, tipo in ((c1, "UA"), (c2, "RTG")):
        v = overall.loc[overall["tipo"] == tipo, metric].sum()
        share = (v / tot * 100) if tot else 0
        fval = money(v) if metric == "revenue_usd" else integer(v)
        col.markdown(theme.kpi_card(f"{tipo} — {LABELS[metric]}", f"{fval}",
                     f"<span style='color:#696A6B'>{share:.1f}% del total</span>"),
                     unsafe_allow_html=True)

    st.markdown("###### Mix UA/RTG por canal")
    top = df.groupby("canal")[metric].sum().nlargest(12).index
    d2 = df[df["canal"].isin(top)].groupby(["canal", "tipo"], as_index=False)[metric].sum()
    order = d2.groupby("canal")[metric].sum().sort_values().index
    fig = px.bar(d2, x=metric, y="canal", color="tipo", orientation="h",
                 category_orders={"canal": list(order)},
                 color_discrete_map={"UA": theme.BLUE, "RTG": theme.PINK},
                 labels={metric: LABELS[metric], "canal": "", "tipo": ""})
    fig.update_layout(height=460, **PLOT, legend=dict(orientation="h", y=1.08))
    st.plotly_chart(fig, use_container_width=True)

    # Evolución temporal por media, filtrando UA o RTG (excluyente)
    st.markdown("###### Evolución temporal por media")
    ca, cb = st.columns([1, 3])
    tipo_sel = ca.radio("Tipo (excluyente)", ["UA", "RTG"], key="q2tipo")
    sub = df[df["tipo"] == tipo_sel].copy()
    canales = sub.groupby("canal")[metric].sum().sort_values(ascending=False).index.tolist()
    sel = cb.multiselect("Medias a mostrar (por default todas)", canales, default=canales,
                         key="q2canales")
    sub = sub[sub["canal"].isin(sel)]
    if sub.empty:
        st.warning("No hay data para ese tipo / esas medias."); return
    sub["fecha"] = pd.to_datetime(sub["dt"].astype(str).str[:10], errors="coerce")
    ev = sub.groupby(["fecha", "canal"], as_index=False)[metric].sum()
    figt = px.line(ev, x="fecha", y=metric, color="canal", markers=True,
                   color_discrete_sequence=theme.CHANNEL_PALETTE * 5,
                   labels={metric: LABELS[metric], "fecha": "", "canal": ""})
    figt.update_layout(height=440, **PLOT, legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(figt, use_container_width=True)


# --------------------------------------------------------------------------- #
# Q3 — Evolución semanal
# --------------------------------------------------------------------------- #
def render_q3(cfg: ClientConfig, start: date, end: date) -> None:
    df, label, live = datasource.get_query(cfg, "q3", start, end)
    _source_caption(label, live)
    if df.empty:
        _empty("q3_evolucion_semanal.sql", "Q3 - Evolucion semanal"); return
    df = coerce_numeric(df, ["installs", "compradores", "revenue_usd"])
    df["semana"] = pd.to_datetime(df["semana"], errors="coerce")
    df = _filter_dates(df, start, end)
    if df.empty:
        st.warning("Sin datos en el período."); return

    metric = st.selectbox("Métrica", ["revenue_usd", "installs", "compradores"],
                          format_func=lambda m: LABELS[m], key="q3m")
    top = df.groupby("canal")[metric].sum().nlargest(8).index.tolist()
    df["canal_top"] = np.where(df["canal"].isin(top), df["canal"], "Otros")
    ev = df.groupby(["semana", "canal_top"], as_index=False)[metric].sum()
    fig = px.area(ev, x="semana", y=metric, color="canal_top",
                  color_discrete_sequence=theme.CHANNEL_PALETTE,
                  labels={metric: LABELS[metric], "semana": "", "canal_top": ""})
    fig.update_layout(height=430, **PLOT, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Q4 — Tasa de repetición
# --------------------------------------------------------------------------- #
def render_q4(cfg: ClientConfig, start: date, end: date) -> None:
    df, label, live = datasource.get_query(cfg, "q4", start, end)
    _source_caption(label, live)
    if df.empty:
        _empty("q4_tasa_repeticion_por_canal_por_mes.sql", "Q4 - Tasa de repeticion"); return
    df = coerce_numeric(df, ["compradores_unicos", "compradores_repetidores",
                             "tasa_repeticion_pct", "ltv_promedio"])
    df = _filter_dates(df, start, end)
    if df.empty:
        st.warning("Sin datos en el período."); return

    # Agrega meses: tasa se recalcula desde las sumas; LTV pondera por compradores.
    g = df.groupby("canal", as_index=False).agg(
        compradores_unicos=("compradores_unicos", "sum"),
        compradores_repetidores=("compradores_repetidores", "sum"),
        ltv_w=("ltv_promedio", lambda s: np.nansum(
            s.values * df.loc[s.index, "compradores_unicos"].values)))
    g["tasa_repeticion_pct"] = 100 * g["compradores_repetidores"] / g["compradores_unicos"].replace(0, np.nan)
    g["ltv_promedio"] = g["ltv_w"] / g["compradores_unicos"].replace(0, np.nan)
    g["es_rocket"] = _rocket_mask(cfg, g["canal"])
    g = g[g["compradores_unicos"] > 0].sort_values("tasa_repeticion_pct", ascending=True)

    fig = px.bar(g.tail(15), x="tasa_repeticion_pct", y="canal", orientation="h",
                 color="es_rocket", color_discrete_map={True: theme.VIOLET, False: theme.GRAY_DK},
                 labels={"tasa_repeticion_pct": LABELS["tasa_repeticion_pct"], "canal": "", "es_rocket": ""})
    fig.update_layout(height=460, **PLOT, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        g[["canal", "compradores_unicos", "compradores_repetidores",
           "tasa_repeticion_pct", "ltv_promedio"]].sort_values("tasa_repeticion_pct", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={
            "tasa_repeticion_pct": st.column_config.NumberColumn(format="%.1f%%"),
            "ltv_promedio": st.column_config.NumberColumn(format="$%.2f")})


# --------------------------------------------------------------------------- #
# Q5 — Journey (qué canal instaló vs cuál convirtió)
# --------------------------------------------------------------------------- #
def render_q5(cfg: ClientConfig, start: date, end: date) -> None:
    df, label, live = datasource.get_query(cfg, "q5", start, end)
    _source_caption(label, live)
    if df.empty:
        _empty("q5_journey_completo_por_dia.sql", "Q5 - Journey"); return
    df = coerce_numeric(df, ["compradores", "revenue_usd"])
    df = _filter_dates(df, start, end)
    if df.empty:
        st.warning("Sin datos en el período."); return

    val = st.selectbox("Valor", ["compradores", "revenue_usd"],
                       format_func=lambda m: LABELS[m], key="q5v")

    # Insight clave: compradores que Rocket instaló y otro canal convirtió.
    total = df[val].sum()
    rocket_install = df[_rocket_mask(cfg, df["install_canal"])][val].sum()
    rocket_assist = df[_rocket_mask(cfg, df["install_canal"]) &
                       ~_rocket_mask(cfg, df["conversion_canal"])][val].sum()
    c1, c2 = st.columns(2)
    sh = (rocket_install / total * 100) if total else 0
    c1.markdown(theme.kpi_card(f"{LABELS[val]} con install de Rocket",
                money(rocket_install) if val == "revenue_usd" else integer(rocket_install),
                f"<span style='color:#696A6B'>{sh:.1f}% del total</span>"), unsafe_allow_html=True)
    c2.markdown(theme.kpi_card("Rocket instaló → otro canal convirtió",
                money(rocket_assist) if val == "revenue_usd" else integer(rocket_assist),
                "<span style='color:#696A6B'>usuarios que Rocket generó y otro cerró</span>"),
                unsafe_allow_html=True)

    st.markdown("###### Matriz install → conversión (top canales)")
    top_i = df.groupby("install_canal")[val].sum().nlargest(8).index
    top_c = df.groupby("conversion_canal")[val].sum().nlargest(8).index
    m = df[df["install_canal"].isin(top_i) & df["conversion_canal"].isin(top_c)]
    piv = m.pivot_table(index="install_canal", columns="conversion_canal",
                        values=val, aggfunc="sum", fill_value=0)
    fig = px.imshow(piv, text_auto=".0f", aspect="auto",
                    color_continuous_scale=["#F5F5F7", theme.VIOLET],
                    labels=dict(x="convirtió", y="instaló", color=LABELS[val]))
    fig.update_layout(height=460, **PLOT)
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------- #
# Q6 — LTV por cohorte
# --------------------------------------------------------------------------- #
def render_q6(cfg: ClientConfig, start: date, end: date) -> None:
    df, label, live = datasource.get_query(cfg, "q6", start, end)
    _source_caption(label, live)
    if df.empty:
        _empty("q6_ltv_por_cohorte_de_instalacion.sql", "Q6 - LTV cohorte"); return
    df = coerce_numeric(df, ["installs", "compradores", "revenue_30d", "revenue_60d",
                             "revenue_total", "ltv_por_install"])
    df = _filter_dates(df, start, end)
    if df.empty:
        st.warning("Sin datos en el período."); return

    g = df.groupby("cohorte_mes", as_index=False).agg(
        installs=("installs", "sum"), compradores=("compradores", "sum"),
        revenue_30d=("revenue_30d", "sum"), revenue_60d=("revenue_60d", "sum"),
        revenue_total=("revenue_total", "sum")).sort_values("cohorte_mes")
    g["ltv_por_install"] = g["revenue_total"] / g["installs"].replace(0, np.nan)

    st.markdown("###### LTV por install, por cohorte de instalación")
    fig = px.line(g, x="cohorte_mes", y="ltv_por_install", markers=True,
                  color_discrete_sequence=[theme.VIOLET],
                  labels={"ltv_por_install": LABELS["ltv_por_install"], "cohorte_mes": ""})
    fig.update_layout(height=340, **PLOT)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("###### Revenue acumulado por cohorte (30d / 60d / total)")
    melt = g.melt(id_vars="cohorte_mes", value_vars=["revenue_30d", "revenue_60d", "revenue_total"],
                  var_name="ventana", value_name="revenue")
    melt["ventana"] = melt["ventana"].map(LABELS)
    fig2 = px.bar(melt, x="cohorte_mes", y="revenue", color="ventana", barmode="group",
                  color_discrete_sequence=[theme.TEAL, theme.BLUE, theme.VIOLET],
                  labels={"revenue": "Revenue (USD)", "cohorte_mes": "", "ventana": ""})
    fig2.update_layout(height=340, **PLOT, legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(g, use_container_width=True, hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="$%.2f")
        for c in ["revenue_30d", "revenue_60d", "revenue_total", "ltv_por_install"]})
