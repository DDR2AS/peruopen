"""Validación de datasets antes de publicar. Funciones puras: devuelven una
lista de errores (vacía = válido) y nunca lanzan."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import duckdb
import pyarrow as pa

from .extractors.bcrp import SERIES
from .registry import DatasetSpec

Validator = Callable[[pa.Table], list[str]]


def validate(spec: DatasetSpec, table: pa.Table, *, today: date | None = None) -> list[str]:
    errors = _generic(spec, table)
    if errors:  # sin el esquema correcto las reglas específicas no tienen sentido
        return errors
    specific = DATASET_VALIDATORS.get(spec.name)
    if specific:
        errors += specific(table, today or datetime.now(UTC).date())
    return errors


def _generic(spec: DatasetSpec, table: pa.Table) -> list[str]:
    errors = []
    expected = spec.arrow_schema()
    if not table.schema.equals(expected):
        errors.append(
            f"Esquema distinto al registro.\n  esperado: {expected}\n  obtenido: {table.schema}"
        )
        return errors
    if table.num_rows < spec.min_records:
        errors.append(f"Solo {table.num_rows} filas (mínimo {spec.min_records})")
    key = ", ".join(f'"{c}"' for c in spec.primary_key)
    nulls = " OR ".join(f'"{c}" IS NULL' for c in spec.primary_key)
    con = duckdb.connect()
    con.register("t", table)
    null_count = con.sql(f"SELECT count(*) FROM t WHERE {nulls}").fetchone()[0]  # type: ignore[index]
    dup_count = con.sql(
        f"SELECT count(*) FROM (SELECT {key} FROM t GROUP BY {key} HAVING count(*) > 1)"
    ).fetchone()[0]  # type: ignore[index]
    if null_count:
        errors.append(f"{null_count} filas con la clave primaria ({key}) vacía")
    if dup_count:
        errors.append(f"{dup_count} claves primarias duplicadas ({key})")
    return errors


def _macro_series(table: pa.Table, today: date) -> list[str]:
    errors = []
    con = duckdb.connect()
    con.register("t", table)
    stats = con.sql(
        "SELECT serie, any_value(frecuencia), max(fecha), min(valor), max(valor) "
        "FROM t GROUP BY serie"
    ).fetchall()
    found = {row[0] for row in stats}
    missing = set(SERIES) - found
    if missing:
        errors.append(f"Faltan series: {sorted(missing)}")
    max_age = {"diaria": timedelta(days=21), "mensual": timedelta(days=200)}
    for serie, frecuencia, last, vmin, vmax in stats:
        if today - last > max_age[frecuencia]:
            errors.append(
                f"{serie}: último dato del {last}, demasiado viejo para una serie {frecuencia}"
            )
        if serie.startswith(("PD04637", "PD04638", "PD04639", "PD04640")) and not (
            vmin > 1 and vmax < 10
        ):
            errors.append(f"{serie}: tipo de cambio fuera de rango [{vmin}, {vmax}]")
    return errors


def _macro_uit(table: pa.Table, today: date) -> list[str]:
    errors = []
    years = table.column("anio").to_pylist()
    values = table.column("valor").to_pylist()
    if years != list(range(years[0], years[-1] + 1)):
        errors.append("Los años de la UIT no son consecutivos")
    if years[-1] < today.year:
        errors.append(
            f"No está la UIT del año en curso ({today.year}); la última es de {years[-1]}"
        )
    if any(b < a for a, b in itertools.pairwise(values)):
        errors.append("La UIT bajó de un año a otro: revisar el parseo")
    if not all(1_000 <= v <= 100_000 for v in values):
        errors.append("Hay valores de UIT fuera del rango razonable [1 000, 100 000]")
    return errors


DATASET_VALIDATORS: dict[str, Callable[[pa.Table, date], list[str]]] = {
    "macro_series": _macro_series,
    "macro_uit": _macro_uit,
}
