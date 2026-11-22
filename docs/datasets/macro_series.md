# `macro_series`: series macroeconómicas del BCRP

**Fuente:** Banco Central de Reserva del Perú, API pública de BCRPData
(`https://estadisticas.bcrp.gob.pe/estadisticas/series/api/`).
**Licencia:** se puede reproducir citando la fuente (condiciones de uso de BCRPData).
**Actualización de la fuente:** diaria (tipo de cambio) y mensual (resto).
**Cobertura:** desde 2000-01-01.

Formato largo: una fila por serie y fecha. Clave primaria: `(serie, fecha)`.

| Columna | Tipo | Descripción |
|---|---|---|
| `serie` | string | Código BCRPData |
| `nombre` | string | Nombre legible |
| `frecuencia` | string | `diaria` o `mensual` |
| `unidad` | string | `S/ por US$`, `%` o `índice` |
| `fecha` | date | Fecha del dato. En series mensuales, el primer día del mes |
| `valor` | float64 | Valor publicado. Los días sin dato (`n.d.`) se omiten |

## Series incluidas

| Código | Serie | Frecuencia |
|---|---|---|
| `PD04637PD` | Tipo de cambio interbancario, compra | diaria |
| `PD04638PD` | Tipo de cambio interbancario, venta | diaria |
| `PD04639PD` | Tipo de cambio bancario SBS, compra | diaria |
| `PD04640PD` | Tipo de cambio bancario SBS, venta | diaria |
| `PN01271PM` | IPC Lima Metropolitana, variación % mensual | mensual |
| `PN01273PM` | IPC Lima Metropolitana, variación % 12 meses | mensual |
| `PN38705PM` | IPC Lima Metropolitana, índice (dic.2021 = 100) | mensual |
| `PD04722MM` | Tasa de referencia de la política monetaria | mensual |
| `PN01770AM` | PBI, índice (2007 = 100) | mensual |
| `PN01728AM` | PBI, variación % interanual | mensual |

## Validaciones antes de publicar

- Están las 10 series.
- El último dato no tiene más de 21 días (diarias) o 200 días (mensuales).
- El tipo de cambio está entre 1 y 10 soles por dólar.
- No hay claves `(serie, fecha)` duplicadas ni vacías.

## Ejemplos

```python
import peruopen as po

po.macro.tipo_cambio(desde="2026-01-01").df()  # interbancario venta
po.macro.tipo_cambio(tipo="sbs", lado="compra").pl()
po.macro.inflacion(periodo="12_meses", desde="2025-01-01").df()
po.query("""
    SELECT year(fecha) AS anio, avg(valor) AS tc_promedio
    FROM macro_series WHERE serie = 'PD04638PD'
    GROUP BY 1 ORDER BY 1
""").df()
```
