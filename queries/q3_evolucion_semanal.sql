-- Q3 — Evolución semanal
-- Installs, compradores y revenue agrupados por semana y canal. Para detectar
-- tendencias y variaciones en el tiempo. Ventana sugerida: 90 días.
SELECT
    date_trunc('week', CAST(substr(dt, 1, 10) AS DATE))              AS semana,
    COALESCE(partner, pid)                                                         AS canal,
    COUNT(DISTINCT CASE WHEN event_name = 'install'           THEN mmp_device_id END)  AS installs,
    COUNT(DISTINCT CASE WHEN event_name = 'cdp_add_on_purchase' THEN mmp_device_id END)  AS compradores,
    SUM(           CASE WHEN event_name = 'cdp_add_on_purchase' THEN event_revenue_usd END)  AS revenue_usd
FROM prod_tracking.postbacks_typed
WHERE app_id IN ('com.univision.prendetv', 'id1531467766')
    AND dt >= date_format(current_date - interval '90' day, '%Y-%m-%d-00')
    AND dt <= date_format(current_date, '%Y-%m-%d-00')
GROUP BY 1, 2
ORDER BY 1, 2
