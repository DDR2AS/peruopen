# 1. Instalar y usar la librería

## Instalar

Recomendado: en un entorno virtual, para no mezclar con otros proyectos.

**Windows (PowerShell o CMD):**

```bash
python -m venv peruopen-env
peruopen-env\Scripts\activate
pip install peruopen
```

**Mac / Linux:**

```bash
python3 -m venv peruopen-env
source peruopen-env/bin/activate
pip install peruopen
```

Para usar los resultados como tablas de pandas o polars, instala también la que prefieras:

```bash
pip install pandas      # o: pip install polars
```

## Primeros pasos

Abre Python (escribe `python` en la terminal) o un notebook de Jupyter:

```python
import peruopen as pe

# ¿Qué datos hay?
pe.list_datasets()

# Valor de la UIT
pe.macro.uit()  # año actual -> 5500
pe.macro.uit(2020)  # -> 4300

# Tipo de cambio diario (S/ por US$)
pe.macro.exchange_rate(start="2026-01-01").df()  # interbancario, venta
pe.macro.exchange_rate(kind="sbs", side="buy", start="2026-11-01").df()

# Inflación de Lima Metropolitana (%), tasa de referencia y PBI
pe.macro.inflation(start="2025-01-01").df()  # variación en 12 meses
pe.macro.inflation(period="monthly", start="2026-01-01").df()
pe.macro.policy_rate(start="2024-01-01").df()
pe.macro.gdp_growth(start="2024-01-01").df()
```

La **primera** consulta tarda unos segundos porque descarga los datos.
Las siguientes son instantáneas: los datos quedan guardados en tu computadora.

## Las series disponibles

peruopen incluye **15 indicadores del BCRP**, verificados y actualizados cada semana:

```python
pe.macro.catalog().df()  # código, descripción, unidad y rango de fechas
```

| Atajo | Qué devuelve |
|---|---|
| `pe.macro.exchange_rate()` | Tipo de cambio (interbancario o SBS, compra o venta) |
| `pe.macro.inflation()` | Inflación de Lima (anual o mensual) |
| `pe.macro.policy_rate()` | Tasa de referencia del BCRP |
| `pe.macro.gdp_growth()` | Crecimiento del PBI |
| `pe.macro.reserves()` | Reservas internacionales netas |
| `pe.macro.unemployment()` | Desempleo de Lima Metropolitana |
| `pe.macro.bank_delinquency()` | Morosidad bancaria |
| `pe.macro.metal_price("copper")` / `("gold")` | Precio del cobre o del oro |
| `pe.macro.series("CÓDIGO")` | Cualquier serie del catálogo por su código |
| `pe.macro.search("palabras")` | Buscar en el catálogo (entiende "dólar", "morosidad"…) |

Todas aceptan `start=` y `end=` para filtrar fechas.

## Elegir el formato del resultado

Todas las consultas devuelven un objeto que se convierte al formato que necesites:

| Quiero… | Agrega al final | Necesita |
|---|---|---|
| Tabla de pandas | `.df()` | `pip install pandas` |
| Tabla de polars | `.pl()` | `pip install polars` |
| Tabla de Arrow | `.arrow()` | nada |
| Lista de tuplas | `.fetchall()` | nada |
| Verlo en pantalla | `.show()` | nada |

## Consultas propias con SQL

Cada dataset es una tabla. Puedes escribir cualquier consulta SQL (dialecto DuckDB):

| Tabla | Contenido |
|---|---|
| `bcrp_catalog` | Descripción, unidad y frecuencia de cada serie del BCRP |
| `bcrp_daily`, `bcrp_monthly` | Datos de las series: `code`, `date`, `value` |
| `sunat_uit` | UIT por año: `year`, `value`, `legal_basis` |

```python
# Tipo de cambio promedio por año
pe.query("""
    SELECT year(date) AS year, round(avg(value), 3) AS fx_avg
    FROM bcrp_daily
    WHERE code = 'PD04638PD'
    GROUP BY 1 ORDER BY 1
""").df()

# Inflación vs. tasa de referencia, con los nombres del catálogo
pe.query("""
    SELECT c.description, d.date, d.value
    FROM bcrp_monthly d JOIN bcrp_catalog c USING (code)
    WHERE d.code IN ('PN01273PM', 'PD04722MM') AND d.date >= DATE '2024-01-01'
    ORDER BY d.date
""").df()

# ¿Cuántos dólares son 10 UIT al tipo de cambio más reciente?
pe.query("""
    SELECT u.value * 10 / fx.value AS dollars
    FROM sunat_uit u,
         (SELECT value FROM bcrp_daily WHERE code = 'PD04638PD'
          ORDER BY date DESC LIMIT 1) fx
    WHERE u.year = year(current_date)
""").fetchone()
```

El detalle de cada tabla está en [docs/datasets/](../datasets/).

## Actualización de los datos

No tienes que hacer nada: la librería revisa **una vez al día** si hay datos
nuevos y los descarga sola.

| Necesito… | Cómo |
|---|---|
| Ver qué versión de los datos tengo | `pe.status()` |
| Buscar datos nuevos ahora mismo | `pe.update()` |
| Trabajar sin internet | variable de entorno `PERUOPEN_OFFLINE=1` |
| Que un análisis dé siempre el mismo resultado | `data = pe.connect(snapshot="...")` y luego `data.query(...)` o `pe.macro.series(..., conn=data)` |
| Borrar los datos descargados | `pe.clear_cache()` |

## Problemas comunes

| Mensaje | Qué hacer |
|---|---|
| `ModuleNotFoundError: No module named 'peruopen'` | Activa el entorno virtual donde lo instalaste (`peruopen-env\Scripts\activate`) |
| `ModuleNotFoundError: No module named 'pandas'` al usar `.df()` | `pip install pandas` |
| `La serie 'XXX' no está incluida en peruopen` | Revisa las series disponibles con `pe.macro.catalog()` |
| `No existe el dataset 'xxx'. ¿Quisiste decir…?` | Revisa el nombre con `pe.list_datasets()` |
| `No se pudo leer la vitrina … y no hay caché` | No hay internet y nunca se descargó nada. Conéctate una vez |
| Advertencia `No se pudo revisar si hay datos nuevos` | Sin internet: está usando los datos que ya tenías. Es normal |
