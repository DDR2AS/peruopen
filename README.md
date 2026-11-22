# peruopen

**Datos públicos oficiales del Perú, curados y versionados, listos para consultar
con una línea de Python o SQL, y sin scraping al ejecutar.**

> 🚧 **Estado: alpha.** La API puede cambiar entre versiones; los cambios se
> anotan en el [CHANGELOG](https://github.com/DDR2AS/peruopen/blob/main/CHANGELOG.md).

## Qué es

peruopen reúne datasets públicos del Estado peruano en archivos **Apache
Parquet** normalizados y validados, con un catálogo único. Se consultan con **DuckDB**, se exportan a Polars o Pandas, y se
exponen a agentes de IA (Claude, Cursor, etc.) mediante un servidor **MCP**.

La diferencia con un scraper: los portales del Estado cambian, se caen o bloquean
IPs. peruopen nunca consulta esos portales al ejecutarse. Un pipeline en CI genera
snapshots versionados y la librería solo lee esos snapshots, que quedan
cacheados en tu máquina.

## Uso

```bash
pip install peruopen
```

> 📘 **¿Primera vez?** Sigue la [guía paso a paso](https://github.com/DDR2AS/peruopen/blob/main/docs/guia/README.md):
> instalar, consultar los datos y conectar peruopen a Claude (MCP).

```python
import peruopen as pe

pe.list_datasets()  # qué hay
pe.macro.uit(2026)  # -> 5500
pe.macro.tipo_cambio(desde="2026-01-01").df()  # pandas (o .pl() para polars)

pe.query("""
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
| Forzar la revisión de datos nuevos | `pe.update()` |
| Ver qué versión tengo | `pe.status()` |
| Trabajar sin internet | `PERUOPEN_OFFLINE=1` |
| Resultados reproducibles | `pe.connect(snapshot="2026-11-22")` |
| Borrar la caché | `pe.clear_cache()` |

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
PERUOPEN_BASE_URL="$PWD/data/vitrina" python -c "import peruopen as pe; print(pe.macro.uit())"
```

## Datasets disponibles

| Dataset | Fuente | Contenido | Detalle |
|---|---|---|---|
| `macro_series` | BCRP | Tipo de cambio (interbancario y SBS), inflación, tasa de referencia y PBI, desde 2000 | [ver](https://github.com/DDR2AS/peruopen/blob/main/docs/datasets/macro_series.md) |
| `macro_uit` | SUNAT | Valor de la UIT por año desde 1994, con su Decreto Supremo | [ver](https://github.com/DDR2AS/peruopen/blob/main/docs/datasets/macro_uit.md) |

## Licencia

El código es MIT (ver [LICENSE](https://github.com/DDR2AS/peruopen/blob/main/LICENSE)). Los **datos** conservan la licencia de
su fuente oficial.
