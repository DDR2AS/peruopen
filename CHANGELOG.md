# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Los **datos** se actualizan aparte (snapshots en la vitrina) y no generan
versiones nuevas del paquete.

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
