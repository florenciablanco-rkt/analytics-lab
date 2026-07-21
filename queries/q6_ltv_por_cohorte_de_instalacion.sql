-- Q6 — Cohorte de LTV (maduración mes a mes)
-- De los devices que instalaron en el mes X, cuánto revenue generaron ELLOS MISMOS
-- en cada mes de compra posterior (incluye recompras de meses siguientes).
-- Una fila por (cohorte de install, canal de install, mes de compra).
-- installs_cohorte = tamaño de la cohorte. Ventana sugerida: 180 días.
WITH installs AS (
    SELECT app_id, mmp_device_id, canal, cohorte_mes FROM (
        SELECT
            app_id,
            mmp_device_id,
            COALESCE(partner, pid)   AS canal,
            substr(dt, 1, 7)         AS cohorte_mes,
            ROW_NUMBER() OVER (PARTITION BY app_id, mmp_device_id ORDER BY dt) AS rn
        FROM prod_tracking.postbacks_typed
        WHERE app_id = 'id1531467766'
            AND event_name = 'install'
            AND dt >= date_format(current_date - interval '180' day, '%Y-%m-%d-00')
            AND dt <= date_format(current_date, '%Y-%m-%d-00')
    )
    WHERE rn = 1
),
cohort_size AS (
    SELECT cohorte_mes, canal, COUNT(DISTINCT mmp_device_id) AS installs_cohorte
    FROM installs
    GROUP BY cohorte_mes, canal
),
purchases AS (
    SELECT app_id, mmp_device_id, substr(dt, 1, 7) AS mes_compra, event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id = 'id1531467766'
        AND event_name = 'cdp_add_on_purchase'
        AND dt >= date_format(current_date - interval '180' day, '%Y-%m-%d-00')
        AND dt <= date_format(current_date, '%Y-%m-%d-00')
)
SELECT
    i.cohorte_mes,
    i.app_id,
    i.canal,
    p.mes_compra,
    cs.installs_cohorte,
    COUNT(DISTINCT p.mmp_device_id)  AS compradores,
    SUM(p.event_revenue_usd)         AS revenue
FROM installs i
JOIN purchases p
    ON  i.mmp_device_id = p.mmp_device_id
    AND i.app_id        = p.app_id
JOIN cohort_size cs
    ON  cs.cohorte_mes = i.cohorte_mes
    AND cs.canal       = i.canal
WHERE p.mes_compra >= i.cohorte_mes
GROUP BY i.cohorte_mes, i.app_id, i.canal, p.mes_compra, cs.installs_cohorte
ORDER BY i.cohorte_mes, p.mes_compra
