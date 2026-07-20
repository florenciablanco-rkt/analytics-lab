-- Q2 — Mix UA vs RTG por canal por día
-- Devices, compradores y revenue separados por tipo de campaña (User
-- Acquisition vs Retargeting, via is_retargeting) para cada canal.
-- Ajustá el intervalo de días según el período deseado.
SELECT
    dt,
    app_id,
    COALESCE(partner, pid)  AS canal,
    is_retargeting,
    COUNT(DISTINCT mmp_device_id)                                                        AS devices,
    COUNT(DISTINCT CASE WHEN event_name = 'cdp_add_on_purchase' THEN mmp_device_id END)  AS compradores,
    SUM(           CASE WHEN event_name = 'cdp_add_on_purchase' THEN event_revenue_usd END)  AS revenue_usd
FROM prod_tracking.postbacks_typed
WHERE app_id IN ('com.univision.prendetv', 'id1531467766')
    AND dt >= date_format(current_date - interval '30' day, '%Y-%m-%d-00')
    AND dt <= date_format(current_date, '%Y-%m-%d-00')
GROUP BY dt, app_id, COALESCE(partner, pid), is_retargeting
ORDER BY dt, canal, is_retargeting
