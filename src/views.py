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
    "recompradores_30d": "Recompradores 30d", "tasa_recompra_30d_pct": "Tasa de recompra 30d (%)",
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
    return s.map(cfg.is_rocket)


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
    sel = cb.multiselect("Medias a mostrar (top 8 por default; agregá las que quieras)",
                         canales, default=canales[:8], key="q2canales")
    sub = sub[sub["canal"].isin(sel)]
    if sub.empty:
        st.warning("No hay data para ese tipo / esas medias."); return
    sub["fecha"] = pd.to_datetime(sub["dt"].astype(str).str[:10], errors="coerce")
    ev = sub.groupby(["fecha", "canal"], as_index=False)[metric].sum()
    figt = px.line(ev, x="fecha", y=metric, color="canal", markers=True,
                   color_discrete_sequence=theme.CHANNEL_PALETTE * 5,
                   labels={metric: LABELS[metric], "fecha": "", "canal": ""})
    yfmt = "$%{y:,.2f}" if metric == "revenue_usd" else "%{y:,.0f}"
    figt.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x|%d-%b-%Y}<br>"
                       + LABELS[metric] + ": " + yfmt + "<extra></extra>")
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
    yfmt = "$%{y:,.2f}" if metric == "revenue_usd" else "%{y:,.0f}"
    fig.update_traces(hovertemplate="<b>%{fullData.name}</b><br>%{x|%d-%b-%Y}<br>"
                      + LABELS[metric] + ": " + yfmt + "<extra></extra>")
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
    df = coerce_numeric(df, ["compradores", "recompradores_30d",
                             "tasa_recompra_30d_pct", "ltv_promedio"])
    df = _filter_dates(df, start, end)
    if df.empty:
        st.warning("Sin datos en el período."); return
    st.caption("Recompra = 2ª compra dentro de 30 días del primer purchase, mismo device y canal.")

    # Agrega cohortes por canal: tasa se recalcula desde sumas; LTV pondera por compradores.
    g = df.groupby("canal", as_index=False).agg(
        compradores=("compradores", "sum"),
        recompradores_30d=("recompradores_30d", "sum"),
        ltv_w=("ltv_promedio", lambda s: np.nansum(
            s.values * df.loc[s.index, "compradores"].values)))
    g["tasa_recompra_30d_pct"] = 100 * g["recompradores_30d"] / g["compradores"].replace(0, np.nan)
    g["ltv_promedio"] = g["ltv_w"] / g["compradores"].replace(0, np.nan)
    g["es_rocket"] = _rocket_mask(cfg, g["canal"])
    g = g[g["compradores"] > 0]

    # KPI Rocket vs resto (recompra ponderada)
    def _rate(sub):
        c, r = sub["compradores"].sum(), sub["recompradores_30d"].sum()
        return (100 * r / c) if c else np.nan
    rk = _rate(g[g["es_rocket"]])
    rest = _rate(g[~g["es_rocket"]])
    c1, c2 = st.columns(2)
    c1.markdown(theme.kpi_card("Recompra 30d — Rocket",
                "—" if np.isnan(rk) else f"{rk:.1f}%"), unsafe_allow_html=True)
    c2.markdown(theme.kpi_card("Recompra 30d — resto",
                "—" if np.isnan(rest) else f"{rest:.1f}%"), unsafe_allow_html=True)

    st.markdown("###### Tasa de recompra 30d por canal")
    gb = g.sort_values("tasa_recompra_30d_pct", ascending=True).tail(15)
    fig = px.bar(gb, x="tasa_recompra_30d_pct", y="canal", orientation="h",
                 color="es_rocket", color_discrete_map={True: theme.VIOLET, False: theme.GRAY_DK},
                 labels={"tasa_recompra_30d_pct": LABELS["tasa_recompra_30d_pct"], "canal": "", "es_rocket": ""})
    fig.update_layout(height=440, **PLOT, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("###### LTV promedio por comprador, por canal")
    gl = g[g["ltv_promedio"].notna()].sort_values("ltv_promedio", ascending=True).tail(15)
    figl = px.bar(gl, x="ltv_promedio", y="canal", orientation="h",
                  color="es_rocket", color_discrete_map={True: theme.VIOLET, False: theme.GRAY_DK},
                  labels={"ltv_promedio": LABELS["ltv_promedio"], "canal": "", "es_rocket": ""})
    figl.update_layout(height=440, **PLOT, showlegend=False)
    st.plotly_chart(figl, use_container_width=True)

    st.dataframe(
        g[["canal", "compradores", "recompradores_30d", "tasa_recompra_30d_pct", "ltv_promedio"]]
        .sort_values("tasa_recompra_30d_pct", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={
            "tasa_recompra_30d_pct": st.column_config.NumberColumn(format="%.1f%%"),
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

    # Aporte de Rocket: de cada canal de conversión, qué % vino de un install de Rocket
    st.markdown("###### Aporte de Rocket a la conversión de cada canal")
    st.caption("De lo que convierte cada canal, qué parte son usuarios que Rocket instaló.")
    conv = df.groupby("conversion_canal", as_index=False)[val].sum().rename(columns={val: "total"})
    assist = (df[_rocket_mask(cfg, df["install_canal"])]
              .groupby("conversion_canal", as_index=False)[val].sum().rename(columns={val: "rocket"}))
    mm = conv.merge(assist, how="left", on="conversion_canal").fillna({"rocket": 0})
    mm["share_rocket_pct"] = 100 * mm["rocket"] / mm["total"].replace(0, np.nan)
    mm = mm[mm["total"] > 0].nlargest(12, "total").sort_values("share_rocket_pct")
    figa = px.bar(mm, x="share_rocket_pct", y="conversion_canal", orientation="h",
                  color_discrete_sequence=[theme.VIOLET],
                  labels={"share_rocket_pct": "% con install de Rocket", "conversion_canal": ""})
    figa.update_traces(hovertemplate="%{y}<br>%{x:.1f}% con install de Rocket<extra></extra>")
    figa.update_layout(height=430, **PLOT)
    st.plotly_chart(figa, use_container_width=True)

    # Top rutas cruzadas (install ≠ conversión): qué canal capitaliza installs de otros
    st.markdown("###### Top rutas install → conversión (cruces entre canales)")
    cross = df[df["install_canal"] != df["conversion_canal"]].copy()
    if not cross.empty:
        cross["ruta"] = cross["install_canal"] + "  →  " + cross["conversion_canal"]
        rr = cross.groupby("ruta", as_index=False)[val].sum().nlargest(12, val).sort_values(val)
        figr = px.bar(rr, x=val, y="ruta", orientation="h",
                      color_discrete_sequence=[theme.BLUE],
                      labels={val: LABELS[val], "ruta": ""})
        figr.update_layout(height=430, **PLOT)
        st.plotly_chart(figr, use_container_width=True)


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

    if "canal" in df.columns:
        seg = st.radio("Segmento", ["Todos", "Rocket", "Resto (no-Rocket)"],
                       horizontal=True, key="q6seg")
        if seg == "Rocket":
            df = df[df["canal"].map(cfg.is_rocket)]
        elif seg.startswith("Resto"):
            df = df[~df["canal"].map(cfg.is_rocket)]
        if df.empty:
            st.warning("Sin datos para ese segmento."); return

    for c in ["revenue_30d", "revenue_60d", "revenue_total"]:
        df[c] = df[c].fillna(0)
    g = df.groupby("cohorte_mes", as_index=False).agg(
        installs=("installs", "sum"), compradores=("compradores", "sum"),
        revenue_30d=("revenue_30d", "sum"), revenue_60d=("revenue_60d", "sum"),
        revenue_total=("revenue_total", "sum")).sort_values("cohorte_mes")
    inst = g["installs"].replace(0, np.nan)
    g["conv_pct"] = 100 * g["compradores"] / inst
    g["ltv_30d"] = g["revenue_30d"] / inst
    g["ltv_60d"] = g["revenue_60d"] / inst
    g["ltv_total"] = g["revenue_total"] / inst

    st.caption("Cohorte = mes del install. Ojo: las cohortes recientes tienen la "
               "ventana de 60d/total incompleta (todavía no maduraron).")

    st.markdown("###### Tabla de cohortes")
    tabla = g[["cohorte_mes", "installs", "compradores", "conv_pct",
               "ltv_30d", "ltv_60d", "ltv_total", "revenue_total"]]
    st.dataframe(tabla, use_container_width=True, hide_index=True, column_config={
        "cohorte_mes": st.column_config.TextColumn("cohorte"),
        "conv_pct": st.column_config.NumberColumn("conv %", format="%.1f%%"),
        "ltv_30d": st.column_config.NumberColumn("LTV 30d", format="$%.3f"),
        "ltv_60d": st.column_config.NumberColumn("LTV 60d", format="$%.3f"),
        "ltv_total": st.column_config.NumberColumn("LTV total", format="$%.3f"),
        "revenue_total": st.column_config.NumberColumn("revenue total", format="$%.0f")})

    st.markdown("###### LTV por install a 30d / 60d / total, por cohorte")
    st.caption("Normalizado por installs → comparable entre cohortes (no depende del tamaño).")
    melt = g.melt(id_vars="cohorte_mes", value_vars=["ltv_30d", "ltv_60d", "ltv_total"],
                  var_name="ventana", value_name="ltv")
    melt["ventana"] = melt["ventana"].map(
        {"ltv_30d": "LTV 30d", "ltv_60d": "LTV 60d", "ltv_total": "LTV total"})
    fig2 = px.bar(melt, x="cohorte_mes", y="ltv", color="ventana", barmode="group",
                  color_discrete_sequence=[theme.TEAL, theme.BLUE, theme.VIOLET],
                  labels={"ltv": "LTV por install (USD)", "cohorte_mes": "cohorte", "ventana": ""})
    fig2.update_layout(height=380, **PLOT, legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)
