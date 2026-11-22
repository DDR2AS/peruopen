"""Núcleo de series del BCRP (BCRPData): las ~17 más usadas.

API: `{API}/{codigo1-codigo2-…}/json/{desde}/{hasta}/esp`, en lotes de hasta
BATCH_SIZE series de la misma frecuencia (la API no permite mezclar frecuencias).

Particularidades de la fuente:
- Periodos en español: diario "02.Ene.25", mensual "Ene.2025". Septiembre es
  "Set" en las diarias y "Sep" en las mensuales. Los años de 2 dígitos son
  seguros: las series diarias del BCRP empiezan en 1991.
- Los valores faltantes vienen como "n.d.".
- La lista de periodos de un lote es la unión de los periodos de sus series, y
  no viene ordenada.
- El JSON se sirve como text/html, y el WAF puede responder HTTP 200 con una
  página de verificación: se valida que el cuerpo empiece con "{" y se reintenta.
- Si un código del lote no existe, la API lo omite y las columnas dejan de
  calzar: se valida que la cantidad de series sea la pedida.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pyarrow as pa

from ..common import BROWSER_UA, ExtractionResult, fetch, write_raw
from ..registry import DatasetSpec

API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
START = date(1990, 1, 1)
BATCH_SIZE = 10
PAUSE_S = 1.0  # cortesía con el servidor entre llamadas


@dataclass(frozen=True)
class CoreSeries:
    code: str
    frequency: str  # "daily" | "monthly"
    unit: str
    description: str
    # Palabras que DEBEN aparecer en el nombre oficial que devuelve la API (sin
    # tildes, en minúsculas). Protege contra series cruzadas o códigos reasignados.
    name_must_contain: tuple[str, ...]


# El núcleo de peruopen: series verificadas a mano, actualizadas cada semana.
CORE: tuple[CoreSeries, ...] = (
    CoreSeries(
        "PD04637PD",
        "daily",
        "S/ por US$",
        "Tipo de cambio interbancario, compra",
        ("interbancario", "compra"),
    ),
    CoreSeries(
        "PD04638PD",
        "daily",
        "S/ por US$",
        "Tipo de cambio interbancario, venta",
        ("interbancario", "venta"),
    ),
    CoreSeries(
        "PD04639PD",
        "daily",
        "S/ por US$",
        "Tipo de cambio bancario (SBS), compra",
        ("sbs", "compra"),
    ),
    CoreSeries(
        "PD04640PD", "daily", "S/ por US$", "Tipo de cambio bancario (SBS), venta", ("sbs", "venta")
    ),
    CoreSeries(
        "PD04650MD",
        "daily",
        "millones de US$",
        "Reservas internacionales netas del BCRP",
        ("reservas internacionales netas",),
    ),
    CoreSeries(
        "PD04701XD",
        "daily",
        "¢US$ por libra",
        "Cobre, cotización internacional (Londres)",
        ("cobre",),
    ),
    CoreSeries(
        "PD04704XD",
        "daily",
        "US$ por onza troy",
        "Oro, cotización internacional (Londres)",
        ("oro",),
    ),
    CoreSeries(
        "PN01271PM",
        "monthly",
        "%",
        "Inflación mensual: IPC Lima Metropolitana, variación % mensual",
        ("precios", "mensual"),
    ),
    CoreSeries(
        "PN01273PM",
        "monthly",
        "%",
        "Inflación anual: IPC Lima Metropolitana, variación % 12 meses",
        ("precios", "12 meses"),
    ),
    CoreSeries(
        "PN38705PM",
        "monthly",
        "índice (dic. 2021 = 100)",
        "IPC Lima Metropolitana, índice",
        ("precios", "2021"),
    ),
    CoreSeries(
        "PD04722MM",
        "monthly",
        "%",
        "Tasa de referencia de la política monetaria del BCRP",
        ("referencia",),
    ),
    CoreSeries(
        "PN01728AM",
        "monthly",
        "%",
        "PBI, variación % respecto al mismo mes del año anterior",
        ("pbi", "variacion"),
    ),
    CoreSeries("PN01770AM", "monthly", "índice (2007 = 100)", "PBI, índice", ("pbi", "2007")),
    CoreSeries(
        "PN38063GM",
        "monthly",
        "%",
        "Tasa de desempleo de Lima Metropolitana (promedio móvil de 3 meses)",
        ("desempleo",),
    ),
    CoreSeries(
        "PN07746EM",
        "monthly",
        "%",
        "Morosidad bancaria: cartera atrasada / colocaciones de las empresas bancarias",
        ("cartera atrasada", "empresas bancarias"),
    ),
)

TABLES = {"daily": "bcrp_daily", "monthly": "bcrp_monthly"}

MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip

DATA_SCHEMA = pa.schema([("code", pa.string()), ("date", pa.date32()), ("value", pa.float64())])


# -- parseo -------------------------------------------------------------------


def _full_year(two_or_four: str, today: date) -> int:
    year = int(two_or_four)
    if year >= 100:
        return year
    return 2000 + year if 2000 + year <= today.year + 1 else 1900 + year


def parse_period(name: str, today: date | None = None) -> date:
    """Periodo de la API -> fecha. '02.Ene.25' -> 2025-01-02 · 'Set.2025' -> 2025-09-01."""
    today = today or datetime.now(UTC).date()
    parts = name.strip().split(".")
    try:
        if len(parts) == 3:
            day, month, year = parts
            return date(_full_year(year, today), MONTHS[month.lower()], int(day))
        if len(parts) == 2:
            month, year = parts
            return date(_full_year(year, today), MONTHS[month.lower()], 1)
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


def official_names(payload: dict[str, Any], codes: list[str]) -> dict[str, str]:
    """Nombre oficial de cada serie, tal como lo devuelve la API."""
    series = payload.get("config", {}).get("series", [])
    return {code: s.get("name", "").strip() for code, s in zip(codes, series, strict=True)}


def _plain(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def check_names(names: dict[str, str]) -> None:
    """Falla si el nombre oficial de alguna serie no es el esperado."""
    expected = {s.code: s.name_must_contain for s in CORE}
    wrong = [
        f"{code}: {name!r} no contiene {list(expected[code])}"
        for code, name in names.items()
        if code in expected and not all(w in _plain(name) for w in expected[code])
    ]
    if wrong:
        raise ValueError(
            "Series del BCRP que no coinciden con lo esperado:\n- " + "\n- ".join(wrong)
        )


# -- descarga -----------------------------------------------------------------


def _api_date(d: date, frequency: str) -> str:
    return d.isoformat() if frequency == "daily" else f"{d.year}-{d.month}"


def _is_json(body: bytes) -> bool:
    return body.lstrip().startswith(b"{")


@dataclass
class BcrpSnapshot:
    tables: dict[str, pa.Table]
    names: dict[str, str]
    raw_files: list[str]
    calls: int
    retrieved_at: datetime


_CACHE: dict[str, BcrpSnapshot] = {}


def download_core(run_id: str) -> BcrpSnapshot:
    """Descarga las series del núcleo una sola vez por corrida."""
    if run_id in _CACHE:
        return _CACHE[run_id]
    today = datetime.now(UTC).date()
    rows: dict[str, list[tuple[str, date, float]]] = {f: [] for f in TABLES}
    names: dict[str, str] = {}
    raw_files: list[str] = []
    calls = 0
    with httpx.Client(
        headers={"User-Agent": BROWSER_UA, "Accept-Language": "es-PE,es;q=0.9"},
        timeout=httpx.Timeout(30.0, read=120.0),
        follow_redirects=True,
    ) as client:
        for frequency in TABLES:
            # La API devuelve las series ORDENADAS POR CÓDIGO, no en el orden pedido:
            # se piden ya ordenadas para que las columnas calcen con los códigos.
            codes = sorted(s.code for s in CORE if s.frequency == frequency)
            for i in range(0, len(codes), BATCH_SIZE):
                batch = codes[i : i + BATCH_SIZE]
                start, end = _api_date(START, frequency), _api_date(today, frequency)
                url = f"{API}/{'-'.join(batch)}/json/{start}/{end}/esp"
                response = fetch(url, what=f"BCRP {frequency}", validate=_is_json, client=client)
                calls += 1
                raw_files.append(
                    str(
                        write_raw("bcrp", run_id, f"{frequency}_{calls:02d}.json", response.content)
                    )
                )
                payload = json.loads(response.content)
                rows[frequency].extend(parse_batch(payload, batch, today))
                batch_names = official_names(payload, batch)
                check_names(batch_names)
                names.update(batch_names)
                time.sleep(PAUSE_S)

    tables = {
        frequency: pa.table(
            {
                "code": [r[0] for r in data],
                "date": [r[1] for r in data],
                "value": [r[2] for r in data],
            },
            schema=DATA_SCHEMA,
        ).sort_by([("code", "ascending"), ("date", "ascending")])
        for frequency, data in rows.items()
    }
    snapshot = BcrpSnapshot(tables, names, raw_files, calls, datetime.now(UTC))
    _CACHE[run_id] = snapshot
    return snapshot


# -- extractores registrados ----------------------------------------------------


def extract_data(spec: DatasetSpec, run_id: str) -> ExtractionResult:
    frequency = spec.name.removeprefix("bcrp_")
    snap = download_core(run_id)
    table = snap.tables[frequency]
    codes = sorted(set(table.column("code").to_pylist()))
    return ExtractionResult(
        dataset=spec.name,
        table=table,
        source_url=API,
        source_mode="live",
        retrieved_at=snap.retrieved_at,
        raw_files=[f for f in snap.raw_files if f"{frequency}_" in f],
        notes=[f"{len(codes)} series: {', '.join(codes)}"],
    )


def extract_catalog(spec: DatasetSpec, run_id: str) -> ExtractionResult:
    snap = download_core(run_id)
    stats: dict[str, tuple[date, date, int]] = {}
    for table in snap.tables.values():
        by_code: dict[str, list[date]] = {}
        for code, when in zip(
            table.column("code").to_pylist(), table.column("date").to_pylist(), strict=True
        ):
            by_code.setdefault(code, []).append(when)
        for code, dates in by_code.items():
            stats[code] = (min(dates), max(dates), len(dates))
    cols: dict[str, list[Any]] = {c.name: [] for c in spec.columns}
    for s in CORE:
        first, last, n = stats.get(s.code, (None, None, 0))
        cols["code"].append(s.code)
        cols["description"].append(s.description)
        cols["name"].append(snap.names.get(s.code) or s.description)
        cols["unit"].append(s.unit)
        cols["frequency"].append(s.frequency)
        cols["table_name"].append(TABLES[s.frequency])
        cols["first_date"].append(first)
        cols["last_date"].append(last)
        cols["observations"].append(n)
    return ExtractionResult(
        dataset=spec.name,
        table=pa.table(cols, schema=spec.arrow_schema()),
        source_url=API,
        source_mode="live",
        retrieved_at=snap.retrieved_at,
        notes=[f"{len(CORE)} series del núcleo, {snap.calls} llamadas a la API"],
    )
