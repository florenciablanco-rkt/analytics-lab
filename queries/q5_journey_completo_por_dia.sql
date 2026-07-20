-- Q5 — Journey completo por día
-- Qué canal hizo el install y cuál se llevó la conversión. Detecta el patrón
-- UA→RTG entre canales sin necesidad de contributors.
-- El CTE de installs NO tiene filtro de fecha, a propósito, para capturar
-- installs históricos fuera del período de conversiones.
WITH installs AS (
    SELECT DISTINCT
        app_id,
        mmp_device_id,
        COALESCE(partner, pid)  AS install_canal
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ('com.univision.prendetv', 'id1531467766')
        AND event_name = 'install'
),
conversions AS (
    SELECT
        dt,
        app_id,
        mmp_device_id,
        COALESCE(partner, pid)  AS conversion_canal,
        event_revenue_usd
    FROM prod_tracking.postbacks_typed
    WHERE app_id IN ('com.univision.prendetv', 'id1531467766')
        AND event_name = 'cdp_add_on_purchase'
        AND dt >= date_format(current_date - interval '30' day, '%Y-%m-%d-00')
        AND dt <= date_format(current_date, '%Y-%m-%d-00')
)
SELECT
    c.dt,
    c.app_id,
    COALESCE(i.install_canal, 'sin_install_registrado')  AS install_canal,
    c.conversion_canal,
    COUNT(DISTINCT c.mmp_device_id)                      AS compradores,
    SUM(c.event_revenue_usd)                              AS revenue_usd
FROM conversions c
LEFT JOIN installs i
    ON  c.mmp_device_id = i.mmp_device_id
    AND c.app_id        = i.app_id
GROUP BY 1, 2, 3, 4
ORDER BY c.dt, compradores DESC
