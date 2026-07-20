-- Q4 — Tasa de repetición por canal por mes
-- Compradores únicos, repetidores y tasa de repetición (%). LTV promedio por
-- comprador incluido. Mensual: la repetición diaria no tiene sentido estadístico.
WITH compras_device AS (
    SELECT
        substr(dt, 1, 7)                AS mes,
        app_id,
        COALESCE(partner, pid)          AS canal,
        mmp_device_id,
        COUNT(*)                         AS num_compras,
        SUM(event_revenue_usd)            AS revenue_total
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ('com.univision.prendetv', 'id1531467766')
        AND event_name = 'cdp_add_on_purchase'
        AND dt >= date_format(current_date - interval '90' day, '%Y-%m-%d-00')
        AND dt <= date_format(current_date, '%Y-%m-%d-00')
    GROUP BY 1, 2, 3, 4
)
SELECT
    mes,
    app_id,
    canal,
    COUNT(DISTINCT mmp_device_id)                                              AS compradores_unicos,
    COUNT(DISTINCT CASE WHEN num_compras > 1 THEN mmp_device_id END)           AS compradores_repetidores,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN num_compras > 1 THEN mmp_device_id END) /
        NULLIF(COUNT(DISTINCT mmp_device_id), 0), 1)                          AS tasa_repeticion_pct,
    AVG(revenue_total)                                                          AS ltv_promedio
FROM compras_device
GROUP BY mes, app_id, canal
ORDER BY mes, compradores_unicos DESC
