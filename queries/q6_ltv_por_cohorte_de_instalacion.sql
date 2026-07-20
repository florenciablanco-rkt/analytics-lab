-- Q6 — LTV por cohorte de instalación (por canal)
-- Revenue acumulado a 30 y 60 días desde el install, por mes de cohorte y canal.
-- Ventana sugerida: 180 días (~3 cohortes mensuales).
WITH installs AS (
    SELECT
        app_id,
        COALESCE(partner, pid)                          AS canal,
        mmp_device_id,
        MIN(date_parse(substr(dt, 1, 10), '%Y-%m-%d'))  AS install_date,
        substr(MIN(dt), 1, 7)                             AS cohorte_mes
    FROM prod_tracking.postbacks_typed
    WHERE app_id = 'id1531467766'
        AND event_name = 'install'
        AND dt >= date_format(current_date - interval '180' day, '%Y-%m-%d-00')
        AND dt <= date_format(current_date, '%Y-%m-%d-00')
    GROUP BY app_id, COALESCE(partner, pid), mmp_device_id
),
purchases AS (
    SELECT
        app_id,
        mmp_device_id,
        date_parse(substr(dt, 1, 10), '%Y-%m-%d')  AS purchase_date,
        event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id = 'id1531467766'
        AND event_name = 'cdp_add_on_purchase'
)
SELECT
    i.cohorte_mes,
    i.app_id,
    i.canal,
    COUNT(DISTINCT i.mmp_device_id)                                                   AS installs,
    COUNT(DISTINCT CASE WHEN p.purchase_date IS NOT NULL THEN i.mmp_device_id END)    AS compradores,
    SUM(CASE WHEN date_diff('day', i.install_date, p.purchase_date) <= 30
             THEN p.event_revenue_usd END)                                              AS revenue_30d,
    SUM(CASE WHEN date_diff('day', i.install_date, p.purchase_date) <= 60
             THEN p.event_revenue_usd END)                                              AS revenue_60d,
    SUM(p.event_revenue_usd)                                                            AS revenue_total,
    SUM(p.event_revenue_usd) / NULLIF(COUNT(DISTINCT i.mmp_device_id), 0)             AS ltv_por_install
FROM installs i
LEFT JOIN purchases p
    ON  i.mmp_device_id = p.mmp_device_id
    AND i.app_id        = p.app_id
GROUP BY i.cohorte_mes, i.app_id, i.canal
ORDER BY i.cohorte_mes, installs DESC
