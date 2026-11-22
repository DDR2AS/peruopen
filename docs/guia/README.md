# Guía para probar peruopen

Estas guías son para **usar** peruopen como cualquier persona: sin clonar el
repo, sin saber cómo funciona por dentro y sin configurar Cloudflare ni GitHub.

| # | Guía | Para qué |
|---|---|---|
| 1 | [Instalar y usar la librería](01-instalar-y-usar.md) | Consultar el tipo de cambio, la inflación o la UIT desde Python |
| 2 | [Conectar peruopen a Claude (MCP)](02-mcp-claude.md) | Preguntarle a Claude por datos del Perú en lenguaje natural |
| 3 | [Script de ejemplo](ejemplos/primeros_pasos.py) | Un archivo listo para correr y ver que todo funciona |

## Requisitos

- **Python 3.11 o superior.** Para comprobarlo: `python --version`.
- Internet la primera vez (para descargar los datos). Después funciona sin conexión.

## ¿Qué datos hay hoy?

| Tabla | Contenido | Fuente |
|---|---|---|
| `bcrp_catalog` | Catálogo de todas las series del BCRP (~17 000): nombre, unidad, frecuencia | BCRP |
| `bcrp_daily`, `bcrp_monthly`, `bcrp_quarterly`, `bcrp_annual` | Datos de todas esas series (tipo de cambio, inflación, tasas, PBI…) | BCRP |
| `sunat_uit` | Valor de la UIT por año desde 1994, con su Decreto Supremo | SUNAT |

El detalle de cada columna está en [docs/datasets/](../datasets/).

## ¿Encontraste un error?

Abre un issue en https://github.com/DDR2AS/peruopen/issues con lo que hiciste,
lo que esperabas y lo que pasó (copia el mensaje de error completo).
