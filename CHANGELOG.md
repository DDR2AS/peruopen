# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Los **datos** se actualizan aparte (snapshots en la vitrina) y no generan
versiones nuevas del paquete.

## [0.1.0a4] - 2026-11-22

### Corregido

- Al actualizar peruopen, la etiqueta de datos en caché (vigente 24 h) podía no
  conocer los datasets nuevos y las consultas fallaban con "Table … does not
  exist" (por ejemplo, en el servidor MCP). Ahora:
  - la etiqueta en caché se descarta cuando cambia la versión de la librería;
  - si una consulta menciona una tabla desconocida, se relee la etiqueta una
    vez y se reintenta.
- `pe.macro.search()` ya no confunde "dólar" con precios en US$, y devuelve
  también el grupo de la serie (`series_group`) para que los nombres cortos
  (p. ej. "IPC") se entiendan.
- El servidor MCP devuelve los errores de SQL como mensaje, sin traceback.

## [0.1.0a3] - 2026-11-22

### Agregado

- **Todas las series del BCRP** (~17 000), no solo 10:
  - `bcrp_catalog`: catálogo con nombre, categoría, unidad, frecuencia, primera y
    última fecha con dato, y si la serie está activa;
  - `bcrp_daily`, `bcrp_monthly`, `bcrp_quarterly`, `bcrp_annual`: los datos
    (`code`, `date`, `value`), separados por frecuencia para que cada consulta
    descargue solo lo que necesita.
- `pe.macro.search("palabras")`: busca series sin importar tildes ni mayúsculas.
- `pe.macro.series(code)`: cualquier serie por su código.
- `pe.macro.policy_rate()` y `pe.macro.gdp_growth()`.
- Tool MCP `search_series` para que los agentes encuentren el código de una serie.

### Cambiado (cambios de API)

- **Nombres de código en inglés.** La documentación sigue en español y los
  valores quedan como los publica el Estado.

  | Antes | Ahora |
  |---|---|
  | `pe.macro.tipo_cambio(desde, hasta, tipo="interbancario", lado="venta")` | `pe.macro.exchange_rate(start, end, kind="interbank", side="sell")` |
  | `tipo="sbs"`, `lado="compra"` | `kind="sbs"`, `side="buy"` |
  | `pe.macro.inflacion(desde, hasta, periodo="12_meses")` | `pe.macro.inflation(start, end, period="12m")` (o `"monthly"`) |
  | `pe.macro.serie(codigo, …)` | `pe.macro.series(code, …)` |
  | `pe.macro.uit(anio)` / `uit_historica()` | `pe.macro.uit(year)` / `uit_history()` |
  | parámetro `pe=` | `conn=` |
  | `build_server(pe=…)` | `build_server(conn=…)` |

- **Datasets renombrados:**
  - `macro_series` (serie, nombre, frecuencia, unidad, fecha, valor) →
    `bcrp_daily` / `bcrp_monthly` (`code`, `date`, `value`) + `bcrp_catalog`;
  - `macro_uit` (anio, valor, base_legal) → `sunat_uit` (`year`, `value`, `legal_basis`).

## [0.1.0a2] - 2026-11-22

### Cambiado

- El alias recomendado es `import peruopen as pe`.
- **Cambio de API:** el parámetro opcional para pasar una conexión en
  `pe.macro.*` y `build_server()` se llama `pe=` (antes `po=`).
- El servidor MCP ya no imprime el banner de FastMCP al arrancar.

### Agregado

- Guía para usuarios en `docs/guia/`: instalar y usar la librería, conectar el
  MCP a Claude Desktop y un script de ejemplo.

## [0.1.0a1] - 2026-11-22

Primera versión publicada (alpha).

### Agregado

- Módulo `macro`:
  - `macro_series`: 10 series del BCRP (tipo de cambio interbancario y SBS,
    inflación, tasa de referencia y PBI) desde 2000;
  - `macro_uit`: UIT por año desde 1994, con su Decreto Supremo.
- Consultas con DuckDB (`pe.query`) y atajos `pe.macro.tipo_cambio`,
  `pe.macro.inflacion` y `pe.macro.uit`.
- Descarga de datos solo cuando se usan, caché local verificada con sha256,
  revisión de datos nuevos cada 24 h, modo offline y versiones fijas por snapshot.
- Servidor MCP de solo lectura (`peruopen-mcp`) con las tools `list_datasets`,
  `describe_dataset` y `query`.

[0.1.0a2]: https://github.com/DDR2AS/peruopen/compare/v0.1.0a1...v0.1.0a2
[0.1.0a1]: https://github.com/DDR2AS/peruopen/releases/tag/v0.1.0a1
