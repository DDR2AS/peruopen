"""Validación de datasets antes de publicar. Funciones puras: devuelven una
lista de errores (vacía = válido) y nunca lanzan."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import duckdb
import pyarrow as pa

from .registry import DatasetSpec

# Series clave que deben existir y estar al día (las usan los atajos de pe.macro).
CORE_SERIES: dict[str, dict[str, timedelta]] = {
    "bcrp_daily": {
        "PD04637PD": timedelta(days=21),  # TC interbancario compra
        "PD04638PD": timedelta(days=21),  # TC interbancario venta
        "PD04639PD": timedelta(days=21),  # TC SBS compra
        "PD04640PD": timedelta(days=21),  # TC SBS venta
    },
    "bcrp_monthly": {
        "PN01271PM": timedelta(days=200),  # IPC var% mensual
        "PN01273PM": timedelta(days=200),  # IPC var% 12 meses
        "PN38705PM": timedelta(days=200),  # IPC índice
        "PD04722MM": timedelta(days=200),  # tasa de referencia
        "PN01770AM": timedelta(days=200),  # PBI índice
        "PN01728AM": timedelta(days=200),  # PBI var%
    },
}
FX_SERIES = ("PD04637PD", "PD04638PD", "PD04639PD", "PD04640PD")
MIN_CATALOG_COVERAGE = 0.80  # al menos 80 % de las series del catálogo con datos


def validate(spec: DatasetSpec, table: pa.Table, *, today: date | None = None) -> list[str]:
    errors = _generic(spec, table)
    if errors:  # sin el esquema correcto las reglas específicas no tienen sentido
        return errors
    specific = DATASET_VALIDATORS.get(spec.name)
    if specific:
        errors += specific(table, today or datetime.now(UTC).date())
    return errors


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> object:
    row = con.sql(sql).fetchone()
    return row[0] if row else None


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
    null_count = _scalar(con, f"SELECT count(*) FROM t WHERE {nulls}")
    dup_count = _scalar(
        con, f"SELECT count(*) FROM (SELECT {key} FROM t GROUP BY {key} HAVING count(*) > 1)"
    )
    if null_count:
        errors.append(f"{null_count} filas con la clave primaria ({key}) vacía")
    if dup_count:
        errors.append(f"{dup_count} claves primarias duplicadas ({key})")
    return errors


def _bcrp_data(name: str) -> Callable[[pa.Table, date], list[str]]:
    def check(table: pa.Table, today: date) -> list[str]:
        errors = []
        con = duckdb.connect()
        con.register("t", table)
        last = dict(con.sql("SELECT code, max(date) FROM t GROUP BY code").fetchall())
        for code, max_age in CORE_SERIES.get(name, {}).items():
            if code not in last:
                errors.append(f"Falta la serie clave {code}")
            elif today - last[code] > max_age:
                errors.append(f"{code}: último dato del {last[code]}, demasiado viejo")
        if name == "bcrp_daily":
            codes = ", ".join(f"'{c}'" for c in FX_SERIES)
            lo, hi = con.sql(
                f"SELECT min(value), max(value) FROM t WHERE code IN ({codes}) "
                "AND date >= DATE '2000-01-01'"
            ).fetchone() or (None, None)
            if lo is not None and not (lo > 1 and hi < 10):
                errors.append(f"Tipo de cambio fuera de rango [{lo}, {hi}]")
        future = _scalar(con, "SELECT count(*) FROM t WHERE date > current_date + INTERVAL 400 DAY")
        if future:
            errors.append(f"{future} filas con fechas en el futuro: revisar el parseo de años")
        return errors

    return check


def _bcrp_catalog(table: pa.Table, today: date) -> list[str]:
    errors = []
    con = duckdb.connect()
    con.register("t", table)
    total = int(_scalar(con, "SELECT count(*) FROM t") or 0)  # type: ignore[call-overload]
    with_data = int(_scalar(con, "SELECT count(*) FROM t WHERE observations > 0") or 0)  # type: ignore[call-overload]
    if total and with_data / total < MIN_CATALOG_COVERAGE:
        errors.append(f"Solo {with_data} de {total} series tienen datos ({with_data / total:.0%})")
    bad_freq = _scalar(
        con,
        "SELECT count(*) FROM t WHERE frequency NOT IN ('daily','monthly','quarterly','annual')",
    )
    if bad_freq:
        errors.append(f"{bad_freq} series con frecuencia desconocida")
    return errors


def _sunat_uit(table: pa.Table, today: date) -> list[str]:
    errors = []
    years = table.column("year").to_pylist()
    values = table.column("value").to_pylist()
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
    "bcrp_catalog": _bcrp_catalog,
    "bcrp_daily": _bcrp_data("bcrp_daily"),
    "bcrp_monthly": _bcrp_data("bcrp_monthly"),
    "bcrp_quarterly": _bcrp_data("bcrp_quarterly"),
    "bcrp_annual": _bcrp_data("bcrp_annual"),
    "sunat_uit": _sunat_uit,
}
