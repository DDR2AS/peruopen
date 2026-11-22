# peruopen

**Datos públicos oficiales del Perú, curados y versionados, listos para consultar
con una línea de Python o SQL, y sin scraping al ejecutar.**

> 🚧 **Estado: pre-alpha.** Ya funcionan el módulo `macro` (BCRP y UIT), la
> librería y el servidor MCP. Todavía no hay versión en PyPI ni vitrina pública.
> Ver [docs/roadmap.md](https://github.com/DDR2AS/peruopen/blob/main/docs/roadmap.md).

## Qué es

peruopen reúne datasets públicos del Estado peruano (SUNAT, BCRP, INEI/RENIEC,
MEF, El Peruano) en archivos **Apache Parquet** normalizados y validados, con un
catálogo único. Se consultan con **DuckDB**, se exportan a Polars o Pandas, y se
exponen a agentes de IA (Claude, Cursor, etc.) mediante un servidor **MCP**.

La diferencia con un scraper: los portales del Estado cambian, se caen o bloquean
IPs. peruopen nunca consulta esos portales al ejecutarse. Un pipeline en CI genera
snapshots versionados y la librería solo lee esos snapshots, que quedan
cacheados en tu máquina.

## Uso

```python
import peruopen as po

po.list_datasets()  # qué hay
po.macro.uit(2026)  # -> 5500
po.macro.tipo_cambio(desde="2026-01-01").df()  # pandas (o .pl() para polars)

po.query("""
    SELECT year(fecha) AS anio, round(avg(valor), 3) AS tc_promedio
    FROM macro_series WHERE serie = 'PD04638PD'
    GROUP BY 1 ORDER BY 1
""").df()
```

La primera vez se descarga solo lo que consultas y queda en caché. Después, la
librería revisa como máximo una vez al día si hay datos nuevos. No hay que hacer
nada para actualizar.

| Necesito… | Cómo |
|---|---|
| Forzar la revisión de datos nuevos | `po.update()` |
| Ver qué versión tengo | `po.status()` |
| Trabajar sin internet | `PERUOPEN_OFFLINE=1` |
| Resultados reproducibles | `po.connect(snapshot="2026-11-22")` |
| Borrar la caché | `po.clear_cache()` |

### Para agentes de IA (MCP)

```json
{"mcpServers": {"peruopen": {"command": "uvx", "args": ["--from", "peruopen[mcp]", "peruopen-mcp"]}}}
```

Expone tres tools: `list_datasets`, `describe_dataset` y `query` (SQL de solo
lectura, sin acceso a otros archivos, con límite de filas y timeout).

### Desarrollo: probar en local sin la nube

```bash
pip install -e ".[pipeline,mcp]"
python -m pipelines run --target local --dir data/vitrina   # cocina + vitrina local
PERUOPEN_BASE_URL="$PWD/data/vitrina" python -c "import peruopen as po; print(po.macro.uit())"
```

## Datasets planificados (v0.1)

| Módulo | Fuente | Contenido |
|---|---|---|
| `calendario` | El Peruano / gob.pe | Feriados y días no laborables, días hábiles 2020–2027 |
| `macro` ✅ | BCRP, SUNAT | Tipo de cambio, inflación, tasa de referencia, PBI, UIT |
| `geo` | INEI / RENIEC | Ubigeos con equivalencias, coordenadas y macrorregión |
| `sunat` | SUNAT | Padrón reducido RUC |

`estado` (MEF y SEACE/OECE) queda para v0.2.

## Proyectos relacionados

- [perudata](https://github.com/cesarchavezp29/perudata): microdatos de encuestas
  del INEI (ENAHO, ENDES…). Complementa a peruopen.
- [horaciochacon/peruopen](https://github.com/horaciochacon/peruopen): paquete
  **R** con el mismo nombre que envuelve el portal CKAN de datosabiertos.gob.pe.
  No tiene relación con este proyecto.

## Licencia

El código es MIT (ver [LICENSE](https://github.com/DDR2AS/peruopen/blob/main/LICENSE)). Los **datos** conservan la licencia de
su fuente oficial.
