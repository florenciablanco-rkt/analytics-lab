"""Constructores de queries de Athena parametrizadas por cliente y fechas.

La fuente es prod_tracking.postbacks_typed (cross-MMP, nivel device).
Notas de sintaxis Athena (Presto/Trino):
  - dt es string tipo '2026-07-17-00'  -> CAST(substr(dt,1,10) AS DATE)
  - filtro de partición sobre dt en formato '%Y-%m-%d-00' (pruning de partición)
  - canal estándar = COALESCE(partner, pid), partner tiene prioridad
"""
from __future__ import annotations

from datetime import date

from .config import ClientConfig


def _in_list(values: list[str]) -> str:
    """Lista de strings SQL-safe para un IN (...). Escapa comillas simples."""
    escaped = [v.replace("'", "''") for v in values]
    return ", ".join(f"'{v}'" for v in escaped)


def _date_filter(start: date, end: date) -> str:
    # dt está particionado como 'YYYY-MM-DD-HH'. Comparamos como string,
    # que respeta el orden cronológico y permite partition pruning.
    return (
        f"    AND dt >= '{start:%Y-%m-%d}-00'\n"
        f"    AND dt <= '{end:%Y-%m-%d}-00'"
    )


def q1_weekly_by_channel(cfg: ClientConfig, start: date, end: date,
                         app_ids: list[str] | None = None) -> str:
    """Q1 — Agregado semanal por canal.

    installs, compradores únicos, total de compras, revenue, ARPI y ticket
    promedio, por semana y canal. Es la query base del dashboard.
    """
    apps = app_ids or cfg.app_ids
    buy = cfg.purchase_event
    inst = cfg.install_event
    return f"""SELECT
    date_trunc('week', CAST(substr(dt, 1, 10) AS DATE))                              AS semana,
    app_id,
    COALESCE(partner, pid)                                                           AS canal,
    COUNT(DISTINCT CASE WHEN event_name = '{inst}' THEN mmp_device_id END)           AS installs,
    COUNT(DISTINCT CASE WHEN event_name = '{buy}'  THEN mmp_device_id END)           AS compradores_unicos,
    COUNT(         CASE WHEN event_name = '{buy}'  THEN 1 END)                        AS total_compras,
    SUM(           CASE WHEN event_name = '{buy}'  THEN event_revenue_usd END)        AS revenue_usd,
    SUM(CASE WHEN event_name = '{buy}' THEN event_revenue_usd END) /
        NULLIF(COUNT(DISTINCT CASE WHEN event_name = '{inst}' THEN mmp_device_id END), 0)  AS arpi,
    SUM(CASE WHEN event_name = '{buy}' THEN event_revenue_usd END) /
        NULLIF(COUNT(CASE WHEN event_name = '{buy}' THEN 1 END), 0)                        AS ticket_promedio
FROM prod_tracking.postbacks_typed
WHERE app_id IN ({_in_list(apps)})
{_date_filter(start, end)}
GROUP BY 1, 2, 3
ORDER BY semana, revenue_usd DESC
"""


# Registro de queries disponibles. Sumar acá las siguientes (Q2..Q6) a medida
# que se porten desde el artifact "queries v1".
QUERIES = {
    "q1_weekly_by_channel": q1_weekly_by_channel,
}
