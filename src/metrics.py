"""Normalización (capa 1) y cálculo Rocket vs. resto (capa 2 del producto).

Regla clave: ARPI y ticket promedio son ratios. Al agregar sobre varias
semanas o canales NUNCA se promedian los ratios: se recalculan a partir de las
sumas (revenue / installs, revenue / compras). Promediar ratios da números mal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ClientConfig

NUMERIC_COLS = [
    "installs", "compradores_unicos", "total_compras",
    "revenue_usd", "arpi", "ticket_promedio",
]


def normalize(df: pd.DataFrame, cfg: ClientConfig) -> pd.DataFrame:
    """Tipa columnas y agrega grupo legible + flags rocket/orgánico (capa 1)."""
    df = df.copy()
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if "semana" in df.columns:
        df["semana"] = pd.to_datetime(df["semana"], errors="coerce")
    df["grupo"] = df["canal"].map(cfg.group_of)
    df["es_rocket"] = df["canal"].map(cfg.is_rocket)
    df["es_organico"] = df["canal"].map(cfg.is_organic)
    return df


def _ratios(installs, compradores, compras, revenue) -> dict:
    return {
        "installs": int(installs),
        "compradores_unicos": int(compradores),
        "total_compras": int(compras),
        "revenue_usd": float(revenue),
        "arpi": float(revenue / installs) if installs else np.nan,
        "ticket_promedio": float(revenue / compras) if compras else np.nan,
        "tasa_compra": float(compradores / installs) if installs else np.nan,
    }


def aggregate_by_channel(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega sobre el período por canal, recalculando ratios desde las sumas."""
    g = df.groupby("canal", as_index=False).agg(
        installs=("installs", "sum"),
        compradores_unicos=("compradores_unicos", "sum"),
        total_compras=("total_compras", "sum"),
        revenue_usd=("revenue_usd", "sum"),
        es_rocket=("es_rocket", "first"),
        es_organico=("es_organico", "first"),
        grupo=("grupo", "first"),
    )
    g["arpi"] = g["revenue_usd"] / g["installs"].replace(0, np.nan)
    g["ticket_promedio"] = g["revenue_usd"] / g["total_compras"].replace(0, np.nan)
    g["tasa_compra"] = g["compradores_unicos"] / g["installs"].replace(0, np.nan)
    return g.sort_values("revenue_usd", ascending=False)


def _pool(sub: pd.DataFrame) -> dict:
    return _ratios(
        sub["installs"].sum(),
        sub["compradores_unicos"].sum(),
        sub["total_compras"].sum(),
        sub["revenue_usd"].sum(),
    )


# Métricas donde "más alto = mejor" para Rocket
HIGHER_IS_BETTER = {"arpi", "ticket_promedio", "tasa_compra"}

METRIC_LABELS = {
    "arpi": "ARPI (revenue por install)",
    "ticket_promedio": "Ticket promedio",
    "tasa_compra": "Tasa de compra (compradores/installs)",
    "revenue_usd": "Revenue (USD)",
    "installs": "Installs",
    "compradores_unicos": "Compradores únicos",
}


def rocket_vs_rest(df: pd.DataFrame, cfg: ClientConfig) -> dict:
    """Compara Rocket contra el promedio del resto de los canales PAGOS.

    El "resto" es el pooled de todos los canales pagos no-Rocket (revenue total
    sobre installs totales, etc.), que es el promedio ponderado real del resto.
    Devuelve, por métrica de calidad: rocket, resto, delta_pct y mejor.
    """
    by_ch = aggregate_by_channel(df)
    rocket = by_ch[by_ch["es_rocket"]]
    paid_rest = by_ch[(~by_ch["es_rocket"]) & (~by_ch["es_organico"])]

    r = _pool(rocket)
    rest = _pool(paid_rest)

    out = {"_rocket_totals": r, "_rest_totals": rest, "metrics": {}}
    for m in ("arpi", "ticket_promedio", "tasa_compra"):
        rv = r.get(m, np.nan)
        rest_v = rest.get(m, np.nan)
        delta = ((rv - rest_v) / rest_v * 100) if rest_v and not np.isnan(rest_v) else np.nan
        better = (rv >= rest_v) if m in HIGHER_IS_BETTER else (rv <= rest_v)
        out["metrics"][m] = {
            "label": METRIC_LABELS[m],
            "rocket": rv,
            "resto": rest_v,
            "delta_pct": delta,
            "mejor": bool(better) if not (np.isnan(rv) or np.isnan(rest_v)) else None,
        }
    return out
