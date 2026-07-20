"""Helpers de formato compartidos por app.py y views.py."""
from __future__ import annotations

import pandas as pd


def money(x) -> str:
    return "—" if pd.isna(x) else f"${x:,.2f}"


def integer(x) -> str:
    return "—" if pd.isna(x) else f"{int(x):,}"


def ratio(x, dec: int = 3) -> str:
    return "—" if pd.isna(x) else f"{x:,.{dec}f}"


def pct(x, dec: int = 1) -> str:
    return "—" if pd.isna(x) else f"{x:+.{dec}f}%"


def fmt_metric(key: str):
    if key in ("ticket_promedio", "revenue_usd", "revenue_30d", "revenue_60d",
               "revenue_total", "ltv_promedio", "ltv_por_install"):
        return money
    if key == "arpi":
        return lambda v: ratio(v, 4)
    if key in ("installs", "compradores_unicos", "total_compras", "compradores",
               "devices", "compradores_repetidores"):
        return integer
    if key == "tasa_repeticion_pct":
        return lambda v: "—" if pd.isna(v) else f"{v:.1f}%"
    return lambda v: ratio(v, 3)


def coerce_numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
