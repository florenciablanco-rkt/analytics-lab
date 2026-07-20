-- Q1 — Agregado por canal por semana
-- Installs, compradores únicos, compras totales, revenue, ARPI y ticket promedio.
-- Una fila por canal por semana. Ventana sugerida: 90 días (~12 semanas).
SELECT
    date_trunc('week', CAST(substr(dt, 1, 10) AS DATE))              AS semana,
    app_id,
    COALESCE(partner, pid)                                                         AS canal,
    COUNT(DISTINCT CASE WHEN event_name = 'install'             THEN mmp_device_id END)  AS installs,
    COUNT(DISTINCT CASE WHEN event_name = 'cdp_add_on_purchase'   THEN mmp_device_id END)  AS compradores_unicos,
    COUNT(         CASE WHEN event_name = 'cdp_add_on_purchase'   THEN 1             END)  AS total_compras,
    SUM(           CASE WHEN event_name = 'cdp_add_on_purchase'   THEN event_revenue_usd END)  AS revenue_usd,
    SUM(CASE WHEN event_name = 'cdp_add_on_purchase' THEN event_revenue_usd END) /
        NULLIF(COUNT(DISTINCT CASE WHEN event_name = 'install' THEN mmp_device_id END), 0)  AS arpi,
    SUM(CASE WHEN event_name = 'cdp_add_on_purchase' THEN event_revenue_usd END) /
        NULLIF(COUNT(CASE WHEN event_name = 'cdp_add_on_purchase' THEN 1 END), 0)           AS ticket_promedio
FROM prod_tracking.postbacks_typed
WHERE app_id IN ('com.univision.prendetv', 'id1531467766')
    AND dt >= date_format(current_date - interval '90' day, '%Y-%m-%d-00')
    AND dt <= date_format(current_date, '%Y-%m-%d-00')
GROUP BY 1, 2, 3
ORDER BY semana, revenue_usd DESC
