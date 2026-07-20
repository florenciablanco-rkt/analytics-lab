"""Conexión a Athena vía PyAthena.

Credenciales: se leen de st.secrets["athena"] (Streamlit Community Cloud) o,
si no existen, de la cadena estándar de boto3 (env vars / perfil AWS local).

Config esperada en .streamlit/secrets.toml:

    [athena]
    aws_access_key_id     = "..."
    aws_secret_access_key = "..."
    region_name           = "us-east-1"
    s3_staging_dir        = "s3://tu-bucket/athena-results/"
    work_group            = "primary"        # opcional
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st


def _secrets() -> dict:
    """Devuelve el bloque [athena] de secrets, o {} si no está definido."""
    try:
        if "athena" in st.secrets:
            return dict(st.secrets["athena"])
    except Exception:
        # st.secrets levanta si no hay ningún secrets.toml; lo tratamos como vacío
        pass
    return {}


def has_credentials() -> bool:
    """True si hay con qué conectarse a Athena (secrets o env de AWS)."""
    s = _secrets()
    if s.get("s3_staging_dir") and (
        s.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
    ):
        return True
    # boto3 puede resolver creds por perfil/rol; exigimos al menos el staging dir
    if os.getenv("ATHENA_S3_STAGING_DIR") and os.getenv("AWS_ACCESS_KEY_ID"):
        return True
    return False


def _connection_kwargs() -> dict:
    s = _secrets()
    return {
        "region_name": s.get("region_name") or os.getenv("AWS_REGION", "us-east-1"),
        "s3_staging_dir": s.get("s3_staging_dir") or os.getenv("ATHENA_S3_STAGING_DIR"),
        "work_group": s.get("work_group") or os.getenv("ATHENA_WORK_GROUP"),
        "aws_access_key_id": s.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": s.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY"),
    }


@st.cache_data(ttl=3600, show_spinner="Consultando Athena…")
def run_query(sql: str) -> pd.DataFrame:
    """Ejecuta una query en Athena y devuelve un DataFrame. Cacheada 1h por SQL."""
    from pyathena import connect  # import lazy: solo necesario en modo vivo

    kwargs = {k: v for k, v in _connection_kwargs().items() if v}
    if not kwargs.get("s3_staging_dir"):
        raise RuntimeError(
            "Falta s3_staging_dir. Configurá el bloque [athena] en secrets."
        )
    conn = connect(**kwargs)
    return pd.read_sql_query(sql, conn)
