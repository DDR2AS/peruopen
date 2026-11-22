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


def titulo(texto: str) -> None:
    print(f"\n=== {texto} ===")


titulo(f"peruopen {pe.__version__}")
for d in pe.list_datasets():
    print(f"- {d['dataset']}: {d['record_count']:,} filas | fuente: {d['source_name']}")

titulo("UIT")
print(f"UIT {2026}: S/ {pe.macro.uit(2026):,}")
print(f"UIT {2015}: S/ {pe.macro.uit(2015):,}")

titulo("Tipo de cambio interbancario (venta), últimos 5 días")
for fecha, valor in pe.macro.tipo_cambio(desde="2026-01-01").fetchall()[-5:]:
    print(f"{fecha}  S/ {valor:.3f}")

titulo("Tipo de cambio promedio por año")
for anio, promedio in pe.query(
    """
    SELECT year(fecha), avg(valor)
    FROM macro_series
    WHERE serie = 'PD04638PD' AND fecha >= '2020-01-01'
    GROUP BY 1 ORDER BY 1
    """
).fetchall():
    print(f"{anio}  S/ {promedio:.3f}")

titulo("Inflación de Lima (variación 12 meses), últimos 6 meses")
for fecha, valor in pe.macro.inflacion().fetchall()[-6:]:
    print(f"{fecha:%Y-%m}  {valor:5.2f} %")

titulo("Estado de los datos")
estado = pe.status()
print(f"Snapshot: {estado['snapshot']}")
print(f"Caché en: {estado['cache_dir']}")
