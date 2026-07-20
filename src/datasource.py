"""Resolución de la fuente de datos, sin subida manual.

Prioridad:
  1. Athena en vivo (si hay credenciales configuradas).
  2. Google Sheet en vivo (si el sheet es accesible por link / gviz CSV).
  3. Snapshot local del sheet (fallback que siempre funciona).
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from . import athena
from .config import ClientConfig
from .queries import q1_weekly_by_channel

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_COLS = {"semana", "app_id", "canal", "installs", "revenue_usd"}


def _valid(df: pd.DataFrame | None) -> bool:
    return df is not None and not df.empty and EXPECTED_COLS.issubset(set(df.columns))


@st.cache_data(ttl=600, show_spinner="Leyendo Google Sheet…")
def _read_gsheet(sheet_id: str, gid: str) -> pd.DataFrame:
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&gid={gid}")
    return pd.read_csv(url)


@st.cache_data(ttl=600)
def _read_snapshot(path: str) -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / path)


@st.cache_data(ttl=1800, show_spinner="Consultando Athena…")
def _read_athena(sql: str) -> pd.DataFrame:
    return athena.run_query(sql)


def get_data(cfg: ClientConfig) -> tuple[pd.DataFrame, str, bool]:
    """Devuelve (df, etiqueta_fuente, es_vivo). Filtra a las apps del cliente."""
    df, label, live = None, "", False

    # 1) Athena
    if athena.has_credentials():
        end = date.today()
        start = end - timedelta(weeks=53)
        try:
            df = _read_athena(q1_weekly_by_channel(cfg, start, end))
            if _valid(df):
                label, live = "Athena (vivo)", True
        except Exception:  # noqa: BLE001
            df = None

    ds = cfg.data_source
    # 2) Google Sheet en vivo
    if not _valid(df) and ds.get("google_sheet_id"):
        try:
            cand = _read_gsheet(ds["google_sheet_id"], ds.get("google_sheet_gid", "0"))
            if _valid(cand):
                df, label, live = cand, "Google Sheet (vivo)", True
        except Exception:  # noqa: BLE001
            df = df

    # 3) Snapshot local
    if not _valid(df) and ds.get("snapshot"):
        df = _read_snapshot(ds["snapshot"])
        label, live = "Snapshot del sheet", False

    if not _valid(df):
        return pd.DataFrame(), "sin datos", False

    df = df[df["app_id"].isin(cfg.app_ids)].copy()
    return df, label, live
