"""Resolución de la fuente de datos por query, sin subida manual.

Cada query (q1..q6) tiene su propia hoja (gid) en el Google Sheet del cliente.
Prioridad por query:
  1. Athena en vivo (si hay credenciales) — corre el builder de esa query.
  2. Tab del Google Sheet (gid) en vivo, si es accesible por link / gviz CSV.
  3. Snapshot local (si está configurado).
  4. Sin datos -> DataFrame vacío (la vista muestra "pegá la data").
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from . import athena, queries
from .config import ClientConfig

REPO_ROOT = Path(__file__).resolve().parent.parent

# Por query: builder de Athena + columnas mínimas esperadas (para validar que
# lo que se leyó del sheet/snapshot es realmente esa query).
QUERY_SPECS = {
    "q1": (queries.q1_weekly_by_channel, {"semana", "canal", "installs", "revenue_usd"}),
    "q2": (queries.q2_mix_ua_rtg,        {"canal", "is_retargeting", "revenue_usd"}),
    "q3": (queries.q3_weekly_evolution,  {"semana", "canal", "installs", "revenue_usd"}),
    "q4": (queries.q4_repeat_rate,       {"canal", "compradores_unicos", "tasa_repeticion_pct"}),
    "q5": (queries.q5_journey,           {"install_canal", "conversion_canal", "compradores"}),
    "q6": (queries.q6_ltv_cohorte,       {"cohorte_mes", "installs", "ltv_por_install"}),
}


def _valid(df: pd.DataFrame | None, cols: set) -> bool:
    return df is not None and not df.empty and cols.issubset(set(df.columns))


@st.cache_data(ttl=600, show_spinner=False)
def _read_gsheet(sheet_id: str, gid: str) -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&gid={gid}")
    return pd.read_csv(url)


@st.cache_data(ttl=600, show_spinner=False)
def _read_snapshot(path: str) -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / path)


@st.cache_data(ttl=1800, show_spinner="Consultando Athena…")
def _read_athena(sql: str) -> pd.DataFrame:
    return athena.run_query(sql)


def get_query(cfg: ClientConfig, key: str, start: date, end: date
              ) -> tuple[pd.DataFrame, str, bool]:
    """Devuelve (df, etiqueta_fuente, es_vivo) para la query `key` (q1..q6)."""
    builder, cols = QUERY_SPECS[key]
    qcfg = cfg.data_source.get("queries", {}).get(key, {})
    df, label, live = None, "", False

    # 1) Athena
    if athena.has_credentials():
        try:
            cand = _read_athena(builder(cfg, start, end))
            if _valid(cand, cols):
                df, label, live = cand, "Athena (vivo)", True
        except Exception:  # noqa: BLE001
            df = None

    # 2) Tab del Google Sheet
    sheet_id = cfg.data_source.get("google_sheet_id")
    if not _valid(df, cols) and sheet_id and qcfg.get("gid"):
        try:
            cand = _read_gsheet(sheet_id, str(qcfg["gid"]))
            if _valid(cand, cols):
                df, label, live = cand, "Google Sheet (vivo)", True
        except Exception:  # noqa: BLE001
            df = df

    # 3) Snapshot local
    if not _valid(df, cols) and qcfg.get("snapshot"):
        try:
            cand = _read_snapshot(qcfg["snapshot"])
            if _valid(cand, cols):
                df, label, live = cand, "Snapshot del sheet", False
        except Exception:  # noqa: BLE001
            df = df

    if not _valid(df, cols):
        return pd.DataFrame(), "sin datos", False

    if "app_id" in df.columns:                     # filtro a las apps del cliente
        df = df[df["app_id"].isin(cfg.app_ids)].copy()
    return df, label, live
