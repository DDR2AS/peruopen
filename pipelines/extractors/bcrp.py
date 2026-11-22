"""Series macroeconómicas del BCRP (API pública de BCRPData).

Endpoint: {API}/{codigo}/json/{desde}/{hasta}/esp

Particularidades verificadas en la Fase 0 (ver docs/fuentes.md):
- Fechas en español: diarias "02.Ene.25", mensuales "Ene.2025". Septiembre es
  "Set" en las diarias y "Sep" en las mensuales.
- Los días sin dato vienen como "n.d.".
- El JSON se sirve como text/html y el WAF puede devolver una página de
  verificación con HTTP 200, así que se valida que el cuerpo empiece con "{".
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pyarrow as pa

from ..common import BROWSER_UA, ExtractionResult, fetch, write_raw
from ..registry import DatasetSpec

API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
START = date(2000, 1, 1)

# código -> (nombre, frecuencia, unidad)
SERIES: dict[str, tuple[str, str, str]] = {
    "PD04637PD": ("Tipo de cambio interbancario - compra", "diaria", "S/ por US$"),
    "PD04638PD": ("Tipo de cambio interbancario - venta", "diaria", "S/ por US$"),
    "PD04639PD": ("Tipo de cambio bancario SBS - compra", "diaria", "S/ por US$"),
    "PD04640PD": ("Tipo de cambio bancario SBS - venta", "diaria", "S/ por US$"),
    "PN01271PM": ("IPC Lima Metropolitana - variación % mensual", "mensual", "%"),
    "PN01273PM": ("IPC Lima Metropolitana - variación % 12 meses", "mensual", "%"),
    "PN38705PM": ("IPC Lima Metropolitana - índice (dic.2021 = 100)", "mensual", "índice"),
    "PD04722MM": ("Tasa de referencia de la política monetaria", "mensual", "%"),
    "PN01770AM": ("PBI - índice (2007 = 100)", "mensual", "índice"),
    "PN01728AM": ("PBI - variación % interanual", "mensual", "%"),
}

MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip


def parse_period(name: str) -> date:
    """'02.Ene.25' -> 2025-01-02 ; 'Set.2025' -> 2025-09-01."""
    parts = name.strip().split(".")
    try:
        if len(parts) == 3:
            day, month, year = parts
            yy = int(year)
            full_year = yy if yy >= 100 else (2000 + yy if yy < 70 else 1900 + yy)
            return date(full_year, MONTHS[month.lower()], int(day))
        if len(parts) == 2:
            month, year = parts
            return date(int(year), MONTHS[month.lower()], 1)
    except (KeyError, ValueError):
        pass
    raise ValueError(f"Formato de periodo BCRP no reconocido: {name!r}")


def parse_value(raw: str) -> float | None:
    text = raw.strip()
    if not text or text.lower() in {"n.d.", "nd", "-"}:
        return None
    value = float(text)
    return value if math.isfinite(value) else None


def parse_payload(payload: dict[str, Any]) -> list[tuple[date, float]]:
    rows = []
    for period in payload.get("periods", []):
        value = parse_value(period["values"][0])
        if value is not None:
            rows.append((parse_period(period["name"]), value))
    return rows


def _is_json(body: bytes) -> bool:
    return body.lstrip().startswith(b"{")


def extract(spec: DatasetSpec, run_id: str) -> ExtractionResult:
    today = datetime.now(UTC).date()
    columns: dict[str, list[Any]] = {c.name: [] for c in spec.columns}
    raw_files, notes = [], []

    with httpx.Client(
        headers={"User-Agent": BROWSER_UA, "Accept-Language": "es-PE,es;q=0.9"},
        timeout=60.0,
        follow_redirects=True,
    ) as client:
        for code, (nombre, frecuencia, unidad) in SERIES.items():
            url = f"{API}/{code}/json/{START.isoformat()}/{today.isoformat()}/esp"
            response = fetch(url, what=f"BCRP {code}", validate=_is_json, client=client)
            raw_files.append(str(write_raw(spec.name, run_id, f"{code}.json", response.content)))
            rows = parse_payload(json.loads(response.content))
            if not rows:
                raise ValueError(f"BCRP {code} no devolvió datos (¿serie descontinuada?)")
            for fecha, valor in rows:
                columns["serie"].append(code)
                columns["nombre"].append(nombre)
                columns["frecuencia"].append(frecuencia)
                columns["unidad"].append(unidad)
                columns["fecha"].append(fecha)
                columns["valor"].append(valor)
            notes.append(f"{code}: {len(rows)} filas, último dato {rows[-1][0].isoformat()}")

    table = pa.table(columns, schema=spec.arrow_schema()).sort_by(
        [("serie", "ascending"), ("fecha", "ascending")]
    )
    return ExtractionResult(
        dataset=spec.name,
        table=table,
        source_url=API,
        source_mode="live",
        raw_files=raw_files,
        notes=notes,
    )
