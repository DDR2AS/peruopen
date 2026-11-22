"""Primeros pasos con peruopen.

Requisitos:
    pip install peruopen

Ejecutar:
    python primeros_pasos.py

La primera vez descarga los datos (unos segundos). Las siguientes, es instantáneo.
"""

import sys

import peruopen as pe

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # tildes en la consola de Windows


def title(text: str) -> None:
    print(f"\n=== {text} ===")


title(f"peruopen {pe.__version__}")
for d in pe.list_datasets():
    print(f"- {d['dataset']}: {d['record_count']:,} filas | fuente: {d['source_name']}")

title("UIT")
print(f"UIT 2026: S/ {pe.macro.uit(2026):,}")
print(f"UIT 2015: S/ {pe.macro.uit(2015):,}")

title("Tipo de cambio interbancario (venta), últimos 5 días")
for day, value in pe.macro.exchange_rate(start="2026-01-01").fetchall()[-5:]:
    print(f"{day}  S/ {value:.3f}")

title("Tipo de cambio promedio por año")
for year, avg in pe.query(
    """
    SELECT year(date), avg(value)
    FROM bcrp_daily
    WHERE code = 'PD04638PD' AND date >= DATE '2020-01-01'
    GROUP BY 1 ORDER BY 1
    """
).fetchall():
    print(f"{year}  S/ {avg:.3f}")

title("Inflación de Lima (variación 12 meses), últimos 6 meses")
for month, value in pe.macro.inflation().fetchall()[-6:]:
    print(f"{month:%Y-%m}  {value:5.2f} %")

title("Buscar series del BCRP: 'morosidad'")
for code, group, name, *_ in pe.macro.search("morosidad", limit=5).fetchall():
    print(f"{code}  {group} - {name}"[:110])

title("Estado de los datos")
status = pe.status()
print(f"Snapshot: {status['snapshot']}")
print(f"Caché en: {status['cache_dir']}")
