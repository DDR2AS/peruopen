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
pe.macro.uit()  # año actual  -> 5500
pe.macro.uit(2020)  # -> 4300

# Tipo de cambio diario (S/ por US$)
pe.macro.tipo_cambio(desde="2026-01-01").df()  # interbancario, venta
pe.macro.tipo_cambio(tipo="sbs", lado="compra", desde="2026-11-01").df()

# Inflación de Lima Metropolitana (%)
pe.macro.inflacion(desde="2025-01-01").df()  # variación en 12 meses
pe.macro.inflacion(periodo="mensual", desde="2026-01-01").df()
```

La **primera** consulta tarda uno o dos segundos porque descarga los datos.
Las siguientes son instantáneas: los datos quedan guardados en tu computadora.

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

```python
# Tipo de cambio promedio por año
pe.query("""
    SELECT year(fecha) AS anio, round(avg(valor), 3) AS tc_promedio
    FROM macro_series
    WHERE serie = 'PD04638PD'
    GROUP BY 1 ORDER BY 1
""").df()

# ¿Cuántos dólares son 10 UIT al tipo de cambio de hoy?
pe.query("""
    SELECT u.valor * 10 / t.valor AS dolares
    FROM macro_uit u,
         (SELECT valor FROM macro_series WHERE serie = 'PD04638PD'
          ORDER BY fecha DESC LIMIT 1) t
    WHERE u.anio = year(current_date)
""").fetchone()
```

Los códigos de las series (`PD04638PD`, etc.) están en
[docs/datasets/macro_series.md](../datasets/macro_series.md). También puedes verlos con:

```python
pe.query("SELECT DISTINCT serie, nombre, frecuencia FROM macro_series ORDER BY 1").df()
```

## Actualización de los datos

No tienes que hacer nada: la librería revisa **una vez al día** si hay datos
nuevos y los descarga sola.

| Necesito… | Cómo |
|---|---|
| Ver qué versión de los datos tengo | `pe.status()` |
| Buscar datos nuevos ahora mismo | `pe.update()` |
| Trabajar sin internet | variable de entorno `PERUOPEN_OFFLINE=1` |
| Que un análisis dé siempre el mismo resultado | `datos = pe.connect(snapshot="2026-11-22")` y luego `datos.query(...)` |
| Borrar los datos descargados | `pe.clear_cache()` |

## Problemas comunes

| Mensaje | Qué hacer |
|---|---|
| `ModuleNotFoundError: No module named 'peruopen'` | Activa el entorno virtual donde lo instalaste (`peruopen-env\Scripts\activate`) |
| `ModuleNotFoundError: No module named 'pandas'` al usar `.df()` | `pip install pandas` |
| `No existe el dataset 'xxx'. ¿Quisiste decir…?` | Revisa el nombre con `pe.list_datasets()` |
| `No se pudo leer la vitrina … y no hay caché` | No hay internet y nunca se descargó nada. Conéctate una vez |
| Advertencia `No se pudo revisar si hay datos nuevos` | Sin internet: está usando los datos que ya tenías. Es normal |
