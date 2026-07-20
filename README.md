# Analytics Lab

Dashboard interno de Rocket Lab que convierte los postbacks del MMP
(`prod_tracking.postbacks_typed`, cross-MMP, nivel device) en una lectura de
**qué tan bien performa Rocket frente al resto de los canales** de cada cliente.

Es la primera pieza del producto Analytics Lab (ver la
[definición de producto](https://docs.google.com/document/d/1eK6QtrlLxpANnJM9OUUADgPzjor9r3hdEW_KOw2jTJI)).
Cubre hoy la capa **Normalizar → Calcular** en modo probabilístico.

## Qué hace

- Corre la query **Q1 — Agregado semanal por canal** parametrizada por cliente,
  apps y **rango de fechas** (se itera por fecha desde la UI, sin copiar/pegar).
- Compara Rocket contra el **pooled de los canales pagos no-Rocket** y la
  **mediana por canal**, en ARPI, ticket promedio y tasa de compra.
- Vistas: comparación Rocket vs resto, ranking por canal, evolución semanal y
  tabla detallada exportable.
- Estilo con el brandbook oficial de Rocket Lab.

## Fuentes de datos

1. **Athena (vivo)** — vía PyAthena. Requiere credenciales (ver abajo).
2. **CSV export** — fallback: subís la salida de Q1 (mismo formato que el sheet).
   Incluye `data/sample_vix.csv` como muestra.

## Correr local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Para datos en vivo, copiá `.streamlit/secrets.toml.example` a
`.streamlit/secrets.toml` y completá el bloque `[athena]`.

## Deploy en Streamlit Community Cloud

1. Push del repo a GitHub.
2. En share.streamlit.io: New app → apuntar a `app.py`.
3. Settings → Secrets → pegar el bloque `[athena]` (mismo formato que el ejemplo).

## Dar de alta un cliente nuevo

Copiar `config/clients/vix.yaml` a `config/clients/<cliente>.yaml` y ajustar
`app_ids`, `purchase_event`, `rocket_channels` y `channel_groups`. La app lo
levanta automáticamente en el selector de cliente. No hace falta tocar código.

## Estructura

```
app.py                     # dashboard Streamlit
config/clients/*.yaml      # config por cliente (eventos, apps, mapeo de canales)
src/config.py              # loader de config
src/queries.py             # queries Athena parametrizadas (Q1; sumar Q2..Q6)
src/athena.py              # conexión PyAthena
src/metrics.py             # normalización + Rocket vs resto
src/theme.py               # brandbook Rocket Lab
data/sample_vix.csv        # muestra para modo CSV
```

## Pendientes conocidos

- **Mapeo de canales de Rocket**: hoy `rocket_channels` solo confirma `rocket`.
  Completar en `vix.yaml` con todos los pids/partners donde corre Rocket
  (bloqueante para que el benchmark sea fiel).
- Portar Q2–Q6 (mix UA/RTG, LTV por cohorte, journey, repetición) desde el
  artifact "queries v1".
- Capas 3 y 4 del producto (Detectar / Recomendar).
