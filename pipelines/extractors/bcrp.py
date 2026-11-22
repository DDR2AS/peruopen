"""Todas las series estadísticas del BCRP (BCRPData).

1. Catálogo oficial: `{BASE}/metadata` (CSV `;`, ~17 000 series).
2. Datos: API `{BASE}/api/{codigo1-codigo2-…}/json/{desde}/{hasta}/esp`, en lotes
   de series de la misma frecuencia (la API no permite mezclar frecuencias).

Particularidades de la fuente:
- El catálogo declara utf-8 pero viene en latin-1 con algunas filas en utf-8:
  se decodifica cada secuencia por separado.
- Periodos en español: diario "02.Ene.25", mensual "Ene.2025", trimestral
  "T1.25", anual "2025". Septiembre es "Set" en las diarias y "Sep" en las
  mensuales. Los años de 2 dígitos son seguros: las series diarias empiezan en
  1991 y las trimestrales en 1978.
- Los valores faltantes vienen como "n.d.".
- La lista de periodos de un lote es la unión de los periodos de sus series, y
  no viene ordenada.
- El JSON se sirve como text/html, y el WAF puede responder HTTP 200 con una
  página de verificación: se valida que el cuerpo empiece con "{" y se reintenta.
- Si un código del lote no existe, la API lo omite y las columnas dejan de
  calzar con los códigos pedidos: el lote se parte en dos hasta aislarlo.
"""

from __future__ import annotations

import codecs
import csv
import io
import json
import logging
import math
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import duckdb
import httpx
import pyarrow as pa

from ..common import BROWSER_UA, ExtractionResult, SourceError, fetch, write_raw
from ..registry import DatasetSpec

log = logging.getLogger("peruopen.pipelines")

BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series"
METADATA_URL = f"{BASE}/metadata"
API = f"{BASE}/api"

FREQUENCIES = {
    "Diaria": "daily",
    "Mensual": "monthly",
    "Trimestral": "quarterly",
    "Anual": "annual",
}
TABLES = {f: f"bcrp_{f}" for f in FREQUENCIES.values()}
BATCH_SIZE = {"daily": 50, "monthly": 100, "quarterly": 100, "annual": 100}
PAUSE_S = 0.4  # cortesía con el servidor entre llamadas

# Una serie está "activa" si su último dato no es más viejo que esto.
ACTIVE_WINDOW = {
    "daily": timedelta(days=60),
    "monthly": timedelta(days=400),
    "quarterly": timedelta(days=550),
    "annual": timedelta(days=900),
}

MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip

codecs.register_error(
    "peruopen_latin1", lambda e: (e.object[e.start : e.end].decode("latin-1"), e.end)
)  # type: ignore[attr-defined]


# -- parseo -------------------------------------------------------------------


def decode_mixed(raw: bytes) -> str:
    """utf-8 donde es válido y latin-1 en el resto (el catálogo mezcla ambos)."""
    return raw.decode("utf-8", errors="peruopen_latin1")


def _full_year(two_or_four: str, today: date) -> int:
    year = int(two_or_four)
    if year >= 100:
        return year
    return 2000 + year if 2000 + year <= today.year + 1 else 1900 + year


def parse_period(name: str, today: date | None = None) -> date:
    """Periodo de la API -> fecha (primer día del mes, trimestre o año).

    '02.Ene.25' -> 2025-01-02 · 'Set.2025' -> 2025-09-01
    'T3.25' -> 2025-07-01 · '2025' -> 2025-01-01
    """
    today = today or datetime.now(UTC).date()
    text = name.strip()
    parts = text.split(".")
    try:
        if len(parts) == 3:
            day, month, year = parts
            return date(_full_year(year, today), MONTHS[month.lower()], int(day))
        if len(parts) == 2 and parts[0].upper().startswith("T"):
            quarter = int(parts[0][1:])
            if not 1 <= quarter <= 4:
                raise ValueError
            return date(_full_year(parts[1], today), 3 * quarter - 2, 1)
        if len(parts) == 2:
            month, year = parts
            return date(_full_year(year, today), MONTHS[month.lower()], 1)
        if len(parts) == 1 and text.isdigit() and len(text) == 4:
            return date(int(text), 1, 1)
    except (KeyError, ValueError):
        pass
    raise ValueError(f"Formato de periodo BCRP no reconocido: {name!r}")


def parse_value(raw: str) -> float | None:
    text = raw.strip()
    if not text or text.lower() in {"n.d.", "nd", "-"}:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _api_date(d: date, frequency: str) -> str:
    if frequency == "daily":
        return d.isoformat()
    if frequency == "monthly":
        return f"{d.year}-{d.month}"
    if frequency == "quarterly":
        return f"{d.year}-{(d.month - 1) // 3 + 1}"
    return str(d.year)


@dataclass
class CatalogRow:
    code: str
    name: str
    category: str
    series_group: str
    unit: str
    frequency: str
    geography: str
    source: str
    publication_group: str
    publishing_area: str
    created_on: date | None
    updated_on: date | None


def _iso_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip()[:10])
    except ValueError:
        return None


def parse_catalog(raw: bytes) -> list[CatalogRow]:
    reader = csv.reader(io.StringIO(decode_mixed(raw)), delimiter=";")
    header = next(reader)
    if not header or not header[0].lower().startswith("c") or len(header) < 17:
        raise ValueError(f"Cabecera del catálogo inesperada: {header[:5]}")
    rows = []
    for r in reader:
        if len(r) < 17 or not r[0].strip():
            continue
        frequency = FREQUENCIES.get(r[10].strip())
        if frequency is None:
            continue
        rows.append(
            CatalogRow(
                code=r[0].strip(),
                category=r[1].strip(),
                series_group=r[2].strip(),
                name=r[3].strip(),
                unit=r[6].strip(),
                geography=r[8].strip(),
                source=r[9].strip(),
                frequency=frequency,
                created_on=_iso_date(r[11]),
                publication_group=r[12].strip(),
                publishing_area=r[13].strip(),
                updated_on=_iso_date(r[14]),
            )
        )
    return rows


def parse_batch(
    payload: dict[str, Any], codes: list[str], today: date
) -> Iterator[tuple[str, date, float]]:
    """Filas (code, date, value) de una respuesta de la API. Lanza ValueError si
    la cantidad de series no calza con los códigos pedidos."""
    series = payload.get("config", {}).get("series", [])
    if len(series) != len(codes):
        raise ValueError(f"La API devolvió {len(series)} series para {len(codes)} códigos")
    for period in payload.get("periods", []):
        when = parse_period(period["name"], today)
        for code, raw in zip(codes, period["values"], strict=True):
            value = parse_value(raw)
            if value is not None:
                yield code, when, value


# -- descarga -----------------------------------------------------------------


def _is_json(body: bytes) -> bool:
    return body.lstrip().startswith(b"{")


def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


@dataclass
class _Download:
    rows: dict[str, list[tuple[str, date, float]]] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    calls: int = 0
    raw_files: list[str] = field(default_factory=list)


def _fetch_batch(
    client: httpx.Client,
    codes: list[str],
    frequency: str,
    today: date,
    run_id: str,
    out: _Download,
    dataset: str,
) -> None:
    start = _api_date(date(1800, 1, 1), frequency)
    end = _api_date(today, frequency)
    url = f"{API}/{'-'.join(codes)}/json/{start}/{end}/esp"
    try:
        response = fetch(
            url, what=f"BCRP lote {frequency}", validate=_is_json, client=client, attempts=5
        )
        out.calls += 1
        rows = list(parse_batch(json.loads(response.content), codes, today))
    except (SourceError, ValueError) as exc:
        if len(codes) == 1:
            log.warning("    serie %s omitida: %s", codes[0], exc)
            out.skipped.append(codes[0])
            return
        mid = len(codes) // 2
        for part in (codes[:mid], codes[mid:]):
            _fetch_batch(client, part, frequency, today, run_id, out, dataset)
        return
    name = f"{frequency}_{out.calls:04d}.json"
    out.raw_files.append(str(write_raw(dataset, run_id, name, response.content)))
    out.rows.setdefault(frequency, []).extend(rows)
    time.sleep(PAUSE_S)


@dataclass
class BcrpSnapshot:
    catalog: list[CatalogRow]
    data: dict[str, pa.Table]
    skipped: list[str]
    calls: int
    raw_files: list[str]
    retrieved_at: datetime


_CACHE: dict[str, BcrpSnapshot] = {}

DATA_SCHEMA = pa.schema([("code", pa.string()), ("date", pa.date32()), ("value", pa.float64())])


def download_all(run_id: str) -> BcrpSnapshot:
    """Descarga catálogo + datos de todas las series una sola vez por corrida."""
    if run_id in _CACHE:
        return _CACHE[run_id]
    today = datetime.now(UTC).date()
    dataset = "bcrp"
    with httpx.Client(
        headers={"User-Agent": BROWSER_UA, "Accept-Language": "es-PE,es;q=0.9"},
        timeout=httpx.Timeout(30.0, read=180.0),
        follow_redirects=True,
    ) as client:
        meta = fetch(
            METADATA_URL,
            what="BCRP catálogo",
            client=client,
            validate=lambda b: b[:1] in (b"C", b"\xef"),
        )
        raw_files = [str(write_raw(dataset, run_id, "metadata.csv", meta.content))]
        catalog = parse_catalog(meta.content)
        out = _Download(raw_files=raw_files)
        for frequency in FREQUENCIES.values():
            codes = sorted(c.code for c in catalog if c.frequency == frequency)
            batches = list(_chunks(codes, BATCH_SIZE[frequency]))
            log.info("  BCRP %s: %s series en %s lotes", frequency, len(codes), len(batches))
            for i, batch in enumerate(batches, 1):
                _fetch_batch(client, batch, frequency, today, run_id, out, dataset)
                if i % 20 == 0:
                    log.info("    %s/%s lotes", i, len(batches))

    data = {}
    for frequency in FREQUENCIES.values():
        rows = out.rows.get(frequency, [])
        table = pa.table(
            {
                "code": [r[0] for r in rows],
                "date": [r[1] for r in rows],
                "value": [r[2] for r in rows],
            },
            schema=DATA_SCHEMA,
        ).sort_by([("code", "ascending"), ("date", "ascending")])
        data[frequency] = table
    snapshot = BcrpSnapshot(
        catalog=catalog,
        data=data,
        skipped=out.skipped,
        calls=out.calls,
        raw_files=out.raw_files,
        retrieved_at=datetime.now(UTC),
    )
    _CACHE[run_id] = snapshot
    return snapshot


# -- extractores registrados ----------------------------------------------------


def extract_data(spec: DatasetSpec, run_id: str) -> ExtractionResult:
    frequency = spec.name.removeprefix("bcrp_")
    snap = download_all(run_id)
    table = snap.data[frequency]
    expected = sum(1 for c in snap.catalog if c.frequency == frequency)
    with_data = len(set(table.column("code").to_pylist()))
    return ExtractionResult(
        dataset=spec.name,
        table=table,
        source_url=API,
        source_mode="live",
        retrieved_at=snap.retrieved_at,
        raw_files=[f for f in snap.raw_files if f"{frequency}_" in f],
        notes=[f"{with_data} de {expected} series del catálogo tienen datos ({frequency})"],
    )


def extract_catalog(spec: DatasetSpec, run_id: str) -> ExtractionResult:
    snap = download_all(run_id)
    today = snap.retrieved_at.date()
    stats: dict[str, tuple[date, date, int]] = {}
    for table in snap.data.values():
        con = duckdb.connect()
        con.register("t", table)
        for code, first, last, n in con.sql(
            "SELECT code, min(date), max(date), count(*) FROM t GROUP BY code"
        ).fetchall():
            stats[code] = (first, last, n)
    cols: dict[str, list[Any]] = {c.name: [] for c in spec.columns}
    for row in snap.catalog:
        first, last, n = stats.get(row.code, (None, None, 0))
        cols["code"].append(row.code)
        cols["name"].append(row.name)
        cols["category"].append(row.category)
        cols["series_group"].append(row.series_group)
        cols["unit"].append(row.unit or None)
        cols["frequency"].append(row.frequency)
        cols["table_name"].append(TABLES[row.frequency])
        cols["first_date"].append(first)
        cols["last_date"].append(last)
        cols["observations"].append(n)
        cols["is_active"].append(bool(last and today - last <= ACTIVE_WINDOW[row.frequency]))
        cols["geography"].append(row.geography or None)
        cols["source"].append(row.source or None)
        cols["publication_group"].append(row.publication_group or None)
        cols["publishing_area"].append(row.publishing_area or None)
        cols["created_on"].append(row.created_on)
        cols["updated_on"].append(row.updated_on)
    table = pa.table(cols, schema=spec.arrow_schema()).sort_by("code")
    notes = [f"{len(snap.catalog)} series, {snap.calls} llamadas a la API"]
    if snap.skipped:
        notes.append(
            f"{len(snap.skipped)} series omitidas por error de la API: {snap.skipped[:20]}"
        )
    return ExtractionResult(
        dataset=spec.name,
        table=table,
        source_url=METADATA_URL,
        source_mode="live",
        retrieved_at=snap.retrieved_at,
        raw_files=[f for f in snap.raw_files if f.endswith("metadata.csv")],
        notes=notes,
    )
