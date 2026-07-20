"""Constructores de queries de Athena parametrizadas por cliente y fechas.

Fuente: prod_tracking.postbacks_typed (cross-MMP, nivel device).
Portadas del artifact "queries v1" (Q1..Q6), parametrizadas por cliente
(app_ids, evento de compra) y rango de fechas.

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
    return (f"    AND dt >= '{start:%Y-%m-%d}-00'\n"
            f"    AND dt <= '{end:%Y-%m-%d}-00'")


# --------------------------------------------------------------------------- #
# Q1 — Agregado por canal por semana
# --------------------------------------------------------------------------- #
def q1_weekly_by_channel(cfg: ClientConfig, start: date, end: date,
                         app_ids: list[str] | None = None) -> str:
    """Installs, compradores únicos, compras, revenue, ARPI y ticket por semana
    y canal. Query base del dashboard."""
    apps = app_ids or cfg.app_ids
    buy, inst = cfg.purchase_event, cfg.install_event
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


# --------------------------------------------------------------------------- #
# Q2 — Mix UA vs RTG por canal por día
# --------------------------------------------------------------------------- #
def q2_mix_ua_rtg(cfg: ClientConfig, start: date, end: date,
                  app_ids: list[str] | None = None) -> str:
    """Devices, compradores y revenue separados por is_retargeting (UA vs RTG),
    por canal y por día."""
    apps = app_ids or cfg.app_ids
    buy = cfg.purchase_event
    return f"""SELECT
    dt,
    app_id,
    COALESCE(partner, pid)                                                           AS canal,
    is_retargeting,
    COUNT(DISTINCT mmp_device_id)                                                    AS devices,
    COUNT(DISTINCT CASE WHEN event_name = '{buy}' THEN mmp_device_id END)            AS compradores,
    SUM(           CASE WHEN event_name = '{buy}' THEN event_revenue_usd END)        AS revenue_usd
FROM prod_tracking.postbacks_typed
WHERE app_id IN ({_in_list(apps)})
{_date_filter(start, end)}
GROUP BY dt, app_id, COALESCE(partner, pid), is_retargeting
ORDER BY dt, canal, is_retargeting
"""


# --------------------------------------------------------------------------- #
# Q3 — Evolución semanal (installs, compradores, revenue)
# --------------------------------------------------------------------------- #
def q3_weekly_evolution(cfg: ClientConfig, start: date, end: date,
                        app_ids: list[str] | None = None) -> str:
    """Installs, compradores y revenue por semana y canal. Para tendencias."""
    apps = app_ids or cfg.app_ids
    buy, inst = cfg.purchase_event, cfg.install_event
    return f"""SELECT
    date_trunc('week', CAST(substr(dt, 1, 10) AS DATE))                              AS semana,
    COALESCE(partner, pid)                                                           AS canal,
    COUNT(DISTINCT CASE WHEN event_name = '{inst}' THEN mmp_device_id END)           AS installs,
    COUNT(DISTINCT CASE WHEN event_name = '{buy}'  THEN mmp_device_id END)           AS compradores,
    SUM(           CASE WHEN event_name = '{buy}'  THEN event_revenue_usd END)        AS revenue_usd
FROM prod_tracking.postbacks_typed
WHERE app_id IN ({_in_list(apps)})
{_date_filter(start, end)}
GROUP BY 1, 2
ORDER BY 1, 2
"""


# --------------------------------------------------------------------------- #
# Q4 — Tasa de repetición por canal por mes
# --------------------------------------------------------------------------- #
def q4_repeat_rate(cfg: ClientConfig, start: date, end: date,
                   app_ids: list[str] | None = None) -> str:
    """Recompra a nivel device dentro de 30 días del primer purchase, por canal
    y cohorte (mes del primer purchase). Más significativa que la repetición por
    mes calendario: mide si el comprador vuelve a comprar en su ventana de 30d."""
    apps = app_ids or cfg.app_ids
    buy = cfg.purchase_event
    return f"""WITH purchases AS (
    SELECT
        app_id,
        COALESCE(partner, pid)                      AS canal,
        mmp_device_id,
        date_parse(substr(dt, 1, 10), '%Y-%m-%d')   AS pdate,
        event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ({_in_list(apps)})
        AND event_name = '{buy}'
{_date_filter(start, end)}
),
first_p AS (
    SELECT app_id, canal, mmp_device_id, MIN(pdate) AS first_date
    FROM purchases
    GROUP BY app_id, canal, mmp_device_id
),
device_stats AS (
    SELECT
        f.app_id, f.canal, f.mmp_device_id,
        substr(CAST(f.first_date AS varchar), 1, 7)  AS cohorte_mes,
        MAX(CASE WHEN p.pdate > f.first_date
                  AND date_diff('day', f.first_date, p.pdate) <= 30
                 THEN 1 ELSE 0 END)                   AS recompro_30d,
        SUM(p.event_revenue_usd)                      AS revenue_device
    FROM first_p f
    JOIN purchases p
        ON  f.mmp_device_id = p.mmp_device_id
        AND f.app_id = p.app_id
        AND f.canal  = p.canal
    GROUP BY f.app_id, f.canal, f.mmp_device_id, substr(CAST(f.first_date AS varchar), 1, 7)
)
SELECT
    cohorte_mes,
    app_id,
    canal,
    COUNT(DISTINCT mmp_device_id)                                     AS compradores,
    SUM(recompro_30d)                                                 AS recompradores_30d,
    ROUND(100.0 * SUM(recompro_30d) / NULLIF(COUNT(DISTINCT mmp_device_id), 0), 1)  AS tasa_recompra_30d_pct,
    AVG(revenue_device)                                               AS ltv_promedio
FROM device_stats
GROUP BY cohorte_mes, app_id, canal
ORDER BY cohorte_mes, compradores DESC
"""


# --------------------------------------------------------------------------- #
# Q5 — Journey completo por día (qué canal instaló vs cuál convirtió)
# --------------------------------------------------------------------------- #
def q5_journey(cfg: ClientConfig, start: date, end: date,
               app_ids: list[str] | None = None) -> str:
    """Cruza install vs conversión por device: detecta el patrón UA→RTG entre
    canales sin contributors. El CTE de installs NO filtra fecha, a propósito,
    para capturar installs históricos fuera del período de conversiones."""
    apps = app_ids or cfg.app_ids
    buy, inst = cfg.purchase_event, cfg.install_event
    return f"""WITH installs AS (
    SELECT DISTINCT
        app_id,
        mmp_device_id,
        COALESCE(partner, pid)  AS install_canal
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ({_in_list(apps)})
        AND event_name = '{inst}'
),
conversions AS (
    SELECT
        dt,
        app_id,
        mmp_device_id,
        COALESCE(partner, pid)  AS conversion_canal,
        event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ({_in_list(apps)})
        AND event_name = '{buy}'
{_date_filter(start, end)}
)
SELECT
    c.dt,
    c.app_id,
    COALESCE(i.install_canal, 'sin_install_registrado')  AS install_canal,
    c.conversion_canal,
    COUNT(DISTINCT c.mmp_device_id)                      AS compradores,
    SUM(c.event_revenue_usd)                             AS revenue_usd
FROM conversions c
LEFT JOIN installs i
    ON  c.mmp_device_id = i.mmp_device_id
    AND c.app_id        = i.app_id
GROUP BY 1, 2, 3, 4
ORDER BY c.dt, compradores DESC
"""


# --------------------------------------------------------------------------- #
# Q6 — LTV por cohorte de instalación (revenue a 30/60 días)
# --------------------------------------------------------------------------- #
def q6_ltv_cohorte(cfg: ClientConfig, start: date, end: date,
                   app_ids: list[str] | None = None) -> str:
    """Revenue acumulado a 30/60 días y total desde el install, por mes de
    cohorte. Sugerido: ventana de installs de ~180 días para 3 cohortes
    mensuales completas. Purchases sin filtro de fecha para no cortar el LTV."""
    apps = app_ids or cfg.app_ids
    buy, inst = cfg.purchase_event, cfg.install_event
    return f"""WITH installs AS (
    SELECT
        app_id,
        mmp_device_id,
        MIN(date_parse(substr(dt, 1, 10), '%Y-%m-%d'))  AS install_date,
        substr(MIN(dt), 1, 7)                           AS cohorte_mes
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ({_in_list(apps)})
        AND event_name = '{inst}'
{_date_filter(start, end)}
    GROUP BY app_id, mmp_device_id
),
purchases AS (
    SELECT
        app_id,
        mmp_device_id,
        date_parse(substr(dt, 1, 10), '%Y-%m-%d')  AS purchase_date,
        event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ({_in_list(apps)})
        AND event_name = '{buy}'
)
SELECT
    i.cohorte_mes,
    i.app_id,
    COUNT(DISTINCT i.mmp_device_id)                                                   AS installs,
    COUNT(DISTINCT CASE WHEN p.purchase_date IS NOT NULL THEN i.mmp_device_id END)    AS compradores,
    SUM(CASE WHEN date_diff('day', i.install_date, p.purchase_date) <= 30
             THEN p.event_revenue_usd END)                                            AS revenue_30d,
    SUM(CASE WHEN date_diff('day', i.install_date, p.purchase_date) <= 60
             THEN p.event_revenue_usd END)                                            AS revenue_60d,
    SUM(p.event_revenue_usd)                                                          AS revenue_total,
    SUM(p.event_revenue_usd) / NULLIF(COUNT(DISTINCT i.mmp_device_id), 0)             AS ltv_por_install
FROM installs i
LEFT JOIN purchases p
    ON  i.mmp_device_id = p.mmp_device_id
    AND i.app_id        = p.app_id
GROUP BY i.cohorte_mes, i.app_id
ORDER BY i.cohorte_mes
"""


# Registro de queries disponibles.
QUERIES = {
    "q1_weekly_by_channel": q1_weekly_by_channel,
    "q2_mix_ua_rtg": q2_mix_ua_rtg,
    "q3_weekly_evolution": q3_weekly_evolution,
    "q4_repeat_rate": q4_repeat_rate,
    "q5_journey": q5_journey,
    "q6_ltv_cohorte": q6_ltv_cohorte,
}
