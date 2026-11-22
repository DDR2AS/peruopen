# Series del BCRP: `bcrp_catalog` y `bcrp_daily` / `bcrp_monthly` / `bcrp_quarterly` / `bcrp_annual`

**Fuente:** Banco Central de Reserva del Perú, BCRPData
(catálogo oficial `estadisticas/series/metadata` y API `estadisticas/series/api`).
**Licencia:** se puede reproducir citando la fuente (condiciones de uso de BCRPData).
**Cobertura:** **todas** las series estadísticas que publica el BCRP (~17 000),
incluidas las históricas y las descontinuadas.

Los datos se separan por frecuencia para que cada consulta descargue solo lo
que necesita: pedir el tipo de cambio baja únicamente `bcrp_daily`.

## `bcrp_catalog`: el catálogo

Una fila por serie. Úsalo para encontrar el código de lo que buscas y saber en
qué tabla están sus datos.

| Columna | Tipo | Descripción |
|---|---|---|
| `code` | string | Código BCRPData (p. ej. `PD04638PD`) |
| `name` | string | Nombre de la serie, tal como lo publica el BCRP |
| `category` | string | Categoría (Tipo de cambio, Empresas bancarias, Balanza comercial…) |
| `series_group` | string | Grupo dentro de la categoría |
| `unit` | string | Unidad de medida, cuando el BCRP la declara |
| `frequency` | string | `daily`, `monthly`, `quarterly` o `annual` |
| `table_name` | string | Tabla con los datos: `bcrp_daily`, `bcrp_monthly`, `bcrp_quarterly` o `bcrp_annual` |
| `first_date` / `last_date` | date | Primera y última fecha con dato |
| `observations` | int64 | Cantidad de datos |
| `is_active` | bool | Último dato reciente para su frecuencia (diaria 60 días, mensual 400, trimestral 550, anual 900) |
| `geography` | string | `PE` (Perú), `RE` (región) u otro valor del BCRP |
| `source` | string | Fuente original declarada por el BCRP |
| `publication_group` / `publishing_area` | string | Grupo de publicación y área del BCRP |
| `created_on` / `updated_on` | date | Creación y última actualización según el BCRP |

## `bcrp_daily`, `bcrp_monthly`, `bcrp_quarterly`, `bcrp_annual`: los datos

Formato largo: una fila por serie y fecha. Clave primaria: `(code, date)`.

| Columna | Tipo | Descripción |
|---|---|---|
| `code` | string | Código de la serie (ver `bcrp_catalog`) |
| `date` | date | Fecha del dato. Mensual: primer día del mes · trimestral: primer día del trimestre · anual: 1 de enero |
| `value` | float64 | Valor publicado. Los periodos sin dato (`n.d.`) se omiten |

## Series usadas por los atajos de `pe.macro`

| Atajo | Código | Serie |
|---|---|---|
| `exchange_rate(kind="interbank", side="buy")` | `PD04637PD` | Tipo de cambio interbancario, compra |
| `exchange_rate()` | `PD04638PD` | Tipo de cambio interbancario, venta |
| `exchange_rate(kind="sbs", side="buy")` | `PD04639PD` | Tipo de cambio bancario SBS, compra |
| `exchange_rate(kind="sbs")` | `PD04640PD` | Tipo de cambio bancario SBS, venta |
| `inflation(period="monthly")` | `PN01271PM` | IPC Lima Metropolitana, variación % mensual |
| `inflation()` | `PN01273PM` | IPC Lima Metropolitana, variación % 12 meses |
| `policy_rate()` | `PD04722MM` | Tasa de referencia de la política monetaria |
| `gdp_growth()` | `PN01728AM` | PBI, variación % interanual |

## Validaciones antes de publicar

- Las series clave de la tabla anterior están presentes y al día.
- El tipo de cambio está entre 1 y 10 soles por dólar.
- No hay fechas en el futuro (control del parseo de años de 2 dígitos).
- Al menos el 80 % de las series del catálogo tienen datos.
- No hay claves `(code, date)` duplicadas ni vacías.

## Ejemplos

```python
import peruopen as pe

# Buscar series (sin importar tildes ni mayúsculas)
pe.macro.search("morosidad").df()
pe.macro.search("exportaciones cobre", frequency="monthly").df()

# Cualquier serie por su código (busca sola la tabla correcta)
pe.macro.series("PN01273PM", start="2020-01-01").df()

# Atajos
pe.macro.exchange_rate(start="2026-01-01").df()
pe.macro.inflation(period="monthly").df()
pe.macro.policy_rate().df()

# SQL con nombres desde el catálogo
pe.query("""
    SELECT c.name, d.date, d.value
    FROM bcrp_monthly d JOIN bcrp_catalog c USING (code)
    WHERE d.code IN ('PN01273PM', 'PD04722MM') AND d.date >= DATE '2024-01-01'
    ORDER BY d.date
""").df()
```
