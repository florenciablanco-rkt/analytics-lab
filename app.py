"""Analytics Lab — dashboard Rocket vs. resto de canales (cliente Vix).

Pestañas: Resumen (Q1) + Mix UA/RTG (Q2), Evolución (Q3), Repetición (Q4),
Journey (Q5) y LTV cohorte (Q6). Cada query lee su hoja del Google Sheet
(o Athena en vivo si hay credenciales). Sin subida manual de archivos.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import plotly.express as px
import streamlit as st

from src import datasource, metrics, theme, views
from src.config import load_client
from src.util import fmt_metric, integer, money, pct

st.set_page_config(page_title="Analytics Lab · Rocket Lab", page_icon="📊", layout="wide")
theme.inject_css()

CLIENT = "vix"
cfg = load_client(CLIENT)

# --------------------------------------------------------------------------- #
# Carga base (Q1) — define el rango de semanas disponible
# --------------------------------------------------------------------------- #
today = date.today()
q1_raw, q1_src, q1_live = datasource.get_query(cfg, "q1", today - timedelta(days=365), today)

theme.header(
    "Analytics Lab —", cfg.name,
    "Rocket vs. el resto de los canales · postbacks del MMP (modo probabilístico)")

if q1_raw.empty:
    st.warning("No hay datos base (Q1) disponibles para este cliente.")
    theme.footer("")
    st.stop()

df_all = metrics.normalize(q1_raw, cfg)
weeks = sorted({p.date() for p in df_all["semana"].dropna()})

# --------------------------------------------------------------------------- #
# Sidebar — filtro de fecha (aplica a todas las vistas)
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### Filtro de fecha")
    mode = st.radio("Modo", ["Rango de fechas", "Semanas (deslizable)"])
    if mode == "Rango de fechas":
        dr = st.date_input("Rango", value=(weeks[0], weeks[-1]),
                           min_value=weeks[0], max_value=weeks[-1])
        start, end = (dr if isinstance(dr, tuple) and len(dr) == 2 else (dr, dr))
    elif len(weeks) > 1:
        start, end = st.select_slider("Semanas", options=weeks, value=(weeks[0], weeks[-1]),
                                      format_func=lambda d: d.strftime("%d-%b-%y"))
    else:
        start = end = weeks[0]
        st.caption(f"Única semana: {weeks[0]:%d-%b-%y}")

    st.markdown("---")
    st.caption(f"Q1: **{q1_src}** {'🟢' if q1_live else '🟡'}")
    st.caption(f"Semanas disponibles: {weeks[0]:%d-%b-%Y} → {weeks[-1]:%d-%b-%Y}")
    st.caption("Cada vista indica su propia fuente.")

df = df_all[(df_all["semana"].dt.date >= start) & (df_all["semana"].dt.date <= end)]

tabs = st.tabs(["📊 Resumen", "🔀 UA vs RTG", "📈 Evolución",
                "🔁 Repetición", "🧭 Journey", "💰 LTV cohorte"])

# =========================================================================== #
# Tab 0 — Resumen (Q1): Rocket vs. resto
# =========================================================================== #
with tabs[0]:
    if df.empty:
        st.warning("No hay datos en el período seleccionado.")
    else:
        st.markdown("#### Rocket Lab vs. resto de canales pagos")
        medias = metrics.paid_medias(df)
        sel_medias = st.multiselect(
            "Comparar Rocket Lab contra (medias)", medias, default=[],
            placeholder="Todas las medias pagas — o elegí una o varias",
            help="Vacío = todas. Los 3 KPIs de abajo se recalculan sobre lo elegido.")
        comp = metrics.rocket_vs_rest(df, cfg, rest_channels=sel_medias or None)
        r_tot = comp["_rocket_totals"]
        wins = sum(1 for m in comp["metrics"].values() if m["mejor"] is True)
        evaluables = sum(1 for m in comp["metrics"].values() if m["mejor"] is not None)

        if r_tot["installs"] == 0:
            st.warning("Rocket Lab no tiene installs en este período. Revisá el mapeo "
                       "de canales de Rocket en la config del cliente.")
        else:
            detalle = ("todos los canales pagos no-Rocket" if not sel_medias
                       else f"{len(sel_medias)} media(s) seleccionada(s)")
            st.markdown(f"Rocket Lab queda **mejor en {wins} de {evaluables}** métricas de "
                        f"calidad. El *resto* es el promedio ponderado de {detalle}.")
            cols = st.columns(3)
            for col, (key, m) in zip(cols, comp["metrics"].items()):
                f = fmt_metric(key)
                if m["mejor"] is None:
                    b = theme.badge("s/d", "neutral")
                else:
                    b = theme.badge(f"{'▲' if m['mejor'] else '▼'} {pct(m['delta_pct'])} vs resto",
                                    "win" if m["mejor"] else "lose")
                col.markdown(theme.kpi_card(
                    m["label"], f(m["rocket"]),
                    f"{b}<br><span style='color:#696A6B'>Resto: {f(m['resto'])}</span>"),
                    unsafe_allow_html=True)

        st.markdown("")
        c1, c2, c3, c4 = st.columns(4)
        tot_rev = df[~df["es_organico"]]["revenue_usd"].sum()
        share = (r_tot["revenue_usd"] / tot_rev * 100) if tot_rev else np.nan
        c1.markdown(theme.kpi_card("Revenue Rocket Lab (total)", money(r_tot["revenue_usd"])), unsafe_allow_html=True)
        c2.markdown(theme.kpi_card("Share de revenue Rocket Lab", pct(share).replace("+", "")), unsafe_allow_html=True)
        c3.markdown(theme.kpi_card("Installs Rocket Lab", integer(r_tot["installs"])), unsafe_allow_html=True)
        c4.markdown(theme.kpi_card("Compradores Rocket Lab", integer(r_tot["compradores_unicos"])), unsafe_allow_html=True)

        st.markdown('<div class="rl-grad-bar"></div>', unsafe_allow_html=True)
        st.markdown("#### Ranking por canal")
        by_ch = metrics.aggregate_by_channel(df)
        metric_opt = st.selectbox(
            "Métrica", ["revenue_usd", "arpi", "ticket_promedio", "tasa_compra",
                        "installs", "compradores_unicos"],
            format_func=lambda m: metrics.METRIC_LABELS[m])
        paid = by_ch[~by_ch["es_organico"]].copy()
        topn = paid.nlargest(15, "revenue_usd").sort_values(metric_opt, ascending=True)
        fig = px.bar(topn, x=metric_opt, y="canal", orientation="h", color="canal",
                     color_discrete_sequence=theme.CHANNEL_PALETTE * 2,
                     labels={metric_opt: metrics.METRIC_LABELS[metric_opt], "canal": ""})
        fig.update_layout(height=470, plot_bgcolor="white", paper_bgcolor="white",
                          font_family="Inter", showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Detalle por canal")
        show = by_ch[["canal", "grupo", "installs", "compradores_unicos", "total_compras",
                      "revenue_usd", "arpi", "ticket_promedio", "tasa_compra"]]
        st.dataframe(show, use_container_width=True, hide_index=True, column_config={
            "revenue_usd": st.column_config.NumberColumn(format="$%.2f"),
            "arpi": st.column_config.NumberColumn(format="%.4f"),
            "ticket_promedio": st.column_config.NumberColumn(format="$%.2f"),
            "tasa_compra": st.column_config.NumberColumn(format="%.4f")})
        st.download_button("Descargar tabla (CSV)", show.to_csv(index=False).encode("utf-8"),
                           file_name=f"analytics_lab_vix_{start}_{end}.csv", mime="text/csv")

with tabs[1]:
    views.render_q2(cfg, start, end)
with tabs[2]:
    views.render_q3(cfg, start, end)
with tabs[3]:
    views.render_q4(cfg, start, end)
with tabs[4]:
    views.render_q5(cfg, start, end)
with tabs[5]:
    views.render_q6(cfg, start, end)

theme.footer(f"{start:%d-%b-%Y} → {end:%d-%b-%Y}")
