-- Q4 — Recompra a 30 días por canal y cohorte (device-level)
-- "Recomprador 30d" = device que hizo una segunda compra dentro de los 30 días
-- de su primer purchase, en el mismo canal. Más significativa que la repetición
-- por mes calendario. Cohorte = mes del primer purchase. Ventana: 90 días.
WITH purchases AS (
    SELECT
        app_id,
        COALESCE(partner, pid)                      AS canal,
        mmp_device_id,
        date_parse(substr(dt, 1, 10), '%Y-%m-%d')   AS pdate,
        event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id = 'id1531467766'
        AND event_name = 'cdp_add_on_purchase'
        AND dt >= date_format(current_date - interval '90' day, '%Y-%m-%d-00')
        AND dt <= date_format(current_date, '%Y-%m-%d-00')
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
