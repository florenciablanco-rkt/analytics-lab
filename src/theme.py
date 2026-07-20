"""Identidad visual RocketLab aplicada a Streamlit (brandbook oficial).

Paleta, tipografía Inter, gradiente holográfico signature y logo R/.
"""
from __future__ import annotations

import streamlit as st

BLACK = "#17191C"
VIOLET = "#7A53CA"
BLUE = "#6592FF"
TEAL = "#72EAE1"
PINK = "#FF6C8E"
GRAY_DK = "#696A6B"
GRAY_LT = "#F5F5F7"
GRAD = "linear-gradient(135deg, #7A53CA 0%, #6592FF 55%, #72EAE1 100%)"

# Colores para categorías/canales en gráficos (paleta de marca)
CHANNEL_PALETTE = [VIOLET, BLUE, TEAL, PINK, "#E8924A", GRAY_DK,
                   "#9B7FE0", "#8FB0FF", "#A7F1EB", "#FF9BB2"]


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        html, body, [class*="css"], .stApp {{ font-family: 'Inter', sans-serif; }}
        .stApp {{ background: {GRAY_LT}; }}
        .block-container {{ padding-top: 1.5rem; max-width: 1250px; }}

        /* Header */
        .rl-header {{
            background: {BLACK}; color: #fff; padding: 26px 34px 22px;
            border-radius: 12px; position: relative; overflow: hidden;
        }}
        .rl-header::before {{
            content: ''; position: absolute; top: 0; right: 0; bottom: 0;
            width: 320px; background: {GRAD}; opacity: 0.14;
            clip-path: polygon(22% 0%, 100% 0%, 100% 100%, 0% 100%);
        }}
        .rl-header-inner {{ position: relative; z-index: 1; }}
        .rl-logo {{
            width: 30px; height: 30px; background: #fff; border-radius: 4px;
            display: inline-flex; align-items: center; justify-content: center;
            font-weight: 800; font-size: 13px; color: {BLACK};
        }}
        .rl-header h1 {{ font-size: 23px; font-weight: 800; letter-spacing: -0.5px; margin: 14px 0 2px; }}
        .rl-grad-text {{ background: {GRAD}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .rl-sub {{ font-size: 12px; color: rgba(255,255,255,0.55); }}
        .rl-grad-bar {{ height: 3px; background: {GRAD}; border-radius: 3px; margin: 10px 0 18px; }}

        /* KPI / comparación */
        .rl-kpi {{
            background: #fff; border-radius: 10px; padding: 16px 18px;
            box-shadow: 0 2px 12px rgba(23,25,28,0.08); position: relative; overflow: hidden;
        }}
        .rl-kpi::after {{
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: {GRAD};
        }}
        .rl-kpi .lbl {{ font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: {GRAY_DK}; font-weight: 600; }}
        .rl-kpi .val {{ font-size: 26px; font-weight: 800; color: {BLACK}; margin-top: 4px; }}
        .rl-kpi .cmp {{ font-size: 12px; margin-top: 6px; }}
        .rl-badge {{ display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
        .rl-badge.win {{ background: #EDFBFA; color: #1CA79A; }}
        .rl-badge.lose {{ background: #FFF0F4; color: {PINK}; }}
        .rl-badge.neutral {{ background: #FAFAFA; color: {GRAY_DK}; }}

        /* Footer */
        .rl-footer {{
            background: {BLACK}; border-radius: 10px; padding: 14px 24px; margin-top: 26px;
            display: flex; justify-content: space-between; align-items: center;
            color: rgba(255,255,255,0.5); font-size: 11px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(title: str, keyword: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="rl-header"><div class="rl-header-inner">
          <div style="display:flex;align-items:center;gap:9px">
            <div class="rl-logo">R/</div>
            <span style="font-size:14px;font-weight:600">Rocket Lab · Analytics Lab</span>
          </div>
          <h1>{title} <span class="rl-grad-text">{keyword}</span></h1>
          <div class="rl-sub">{subtitle}</div>
        </div></div>
        <div class="rl-grad-bar"></div>
        """,
        unsafe_allow_html=True,
    )


def footer(period: str) -> None:
    st.markdown(
        f"""
        <div class="rl-footer">
          <div style="display:flex;align-items:center;gap:8px">
            <div class="rl-logo" style="width:22px;height:22px;font-size:10px">R/</div>
            <span>Rocket Lab · Análisis interno · modo probabilístico</span>
          </div>
          <div style="color:rgba(255,255,255,0.35)">{period}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, comparison_html: str = "") -> str:
    return (
        f'<div class="rl-kpi"><div class="lbl">{label}</div>'
        f'<div class="val">{value}</div>'
        f'<div class="cmp">{comparison_html}</div></div>'
    )


def badge(text: str, kind: str) -> str:
    return f'<span class="rl-badge {kind}">{text}</span>'
