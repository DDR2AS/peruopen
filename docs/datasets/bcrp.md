# Indicadores del BCRP: `bcrp_catalog`, `bcrp_daily` y `bcrp_monthly`

**Fuente:** Banco Central de Reserva del Perú, BCRPData (API `estadisticas/series/api`).
**Licencia:** se puede reproducir citando la fuente (condiciones de uso de BCRPData).
**Actualización:** semanal.

peruopen incluye un **núcleo de 15 series** verificadas a mano: las más usadas
para seguir la economía peruana. Cada serie se valida contra su nombre oficial
en cada actualización.

## Series incluidas

| Código | Serie | Unidad | Frecuencia | Desde | Atajo |
|---|---|---|---|---|---|
| `PD04637PD` | Tipo de cambio interbancario, compra | S/ por US$ | diaria | 1997 | `exchange_rate(side="buy")` |
| `PD04638PD` | Tipo de cambio interbancario, venta | S/ por US$ | diaria | 1997 | `exchange_rate()` |
| `PD04639PD` | Tipo de cambio bancario (SBS), compra | S/ por US$ | diaria | 1997 | `exchange_rate(kind="sbs", side="buy")` |
| `PD04640PD` | Tipo de cambio bancario (SBS), venta | S/ por US$ | diaria | 1997 | `exchange_rate(kind="sbs")` |
| `PD04650MD` | Reservas internacionales netas del BCRP | millones de US$ | diaria | 1999 | `reserves()` |
| `PD04701XD` | Cobre, cotización internacional (Londres) | ¢US$ por libra | diaria | 1997 | `metal_price("copper")` |
| `PD04704XD` | Oro, cotización internacional (Londres) | US$ por onza troy | diaria | 1997 | `metal_price("gold")` |
| `PN01271PM` | Inflación mensual: IPC Lima Metropolitana, variación % mensual | % | mensual | 2003 | `inflation(period="monthly")` |
| `PN01273PM` | Inflación anual: IPC Lima Metropolitana, variación % 12 meses | % | mensual | 1990 | `inflation()` |
| `PN38705PM` | IPC Lima Metropolitana, índice | índice (dic. 2021 = 100) | mensual | 1990 | — |
| `PD04722MM` | Tasa de referencia de la política monetaria del BCRP | % | mensual | 1995 | `policy_rate()` |
| `PN01728AM` | PBI, variación % respecto al mismo mes del año anterior | % | mensual | 1994 | `gdp_growth()` |
| `PN01770AM` | PBI, índice | índice (2007 = 100) | mensual | 2001 | — |
| `PN38063GM` | Tasa de desempleo de Lima Metropolitana (promedio móvil de 3 meses) | % | mensual | 2001 | `unemployment()` |
| `PN07746EM` | Morosidad bancaria: cartera atrasada / colocaciones de las empresas bancarias | % | mensual | 1991 | `bank_delinquency()` |

El desempleo es el de **Lima Metropolitana**: el BCRP no publica una tasa
mensual nacional.

## `bcrp_catalog`

Una fila por serie del núcleo.

| Columna | Tipo | Descripción |
|---|---|---|
| `code` | string | Código BCRPData |
| `description` | string | Qué mide la serie, en lenguaje claro |
| `name` | string | Nombre oficial, tal como lo publica el BCRP |
| `unit` | string | Unidad de medida |
| `frequency` | string | `daily` o `monthly` |
| `table_name` | string | Tabla con los datos: `bcrp_daily` o `bcrp_monthly` |
| `first_date` / `last_date` | date | Primera y última fecha con dato |
| `observations` | int64 | Cantidad de datos |

## `bcrp_daily` y `bcrp_monthly`

Formato largo: una fila por serie y fecha. Clave primaria: `(code, date)`.

| Columna | Tipo | Descripción |
|---|---|---|
| `code` | string | Código de la serie (ver `bcrp_catalog`) |
| `date` | date | Fecha del dato. En `bcrp_monthly`, el primer día del mes |
| `value` | float64 | Valor publicado. Los periodos sin dato (`n.d.`) se omiten |

## Validaciones antes de publicar

- El nombre oficial de cada serie contiene las palabras esperadas (por ejemplo,
  `PD04722MM` debe decir "Referencia"). Así se detectan series cruzadas o códigos
  que el BCRP reasigne.
- Todas las series del núcleo están presentes y al día (diarias: máximo 21 días
  de antigüedad; mensuales: 200 días).
- El tipo de cambio está entre 1 y 10 soles por dólar.
- No hay claves `(code, date)` duplicadas ni vacías.

## Ejemplos

```python
import peruopen as pe

pe.macro.catalog().df()  # las 15 series, con unidad y fechas

pe.macro.exchange_rate(start="2026-01-01").df()
pe.macro.inflation(period="monthly").df()
pe.macro.reserves(start="2026-01-01").df()
pe.macro.metal_price("copper", start="2025-01-01").df()
pe.macro.series("PN38705PM").df()  # cualquier serie del núcleo por su código

# SQL con descripción y unidad desde el catálogo
pe.query("""
    SELECT c.description, c.unit, d.date, d.value
    FROM bcrp_monthly d JOIN bcrp_catalog c USING (code)
    WHERE d.code IN ('PN01273PM', 'PD04722MM') AND d.date >= DATE '2024-01-01'
    ORDER BY d.date
""").df()
```
