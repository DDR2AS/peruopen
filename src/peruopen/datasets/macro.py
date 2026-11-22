"""Atajos para datos macroeconómicos: todas las series del BCRP y la UIT.

import peruopen as pe
pe.macro.search("morosidad")                       # encontrar el código de una serie
pe.macro.series("PN01271PM", start="2025-01-01")   # cualquier serie por su código
pe.macro.exchange_rate(start="2026-01-01").df()    # tipo de cambio
pe.macro.uit(2026)                                 # -> 5500
"""

from __future__ import annotations

from datetime import date
from typing import Literal

import duckdb

from ..engine import PeruOpen

EXCHANGE_RATE = {
    ("interbank", "buy"): "PD04637PD",
    ("interbank", "sell"): "PD04638PD",
    ("sbs", "buy"): "PD04639PD",
    ("sbs", "sell"): "PD04640PD",
}
INFLATION = {"monthly": "PN01271PM", "12m": "PN01273PM"}
POLICY_RATE = "PD04722MM"
GDP_GROWTH = "PN01728AM"

DateLike = str | date | None

# Palabras de uso común que el BCRP nombra de otra forma. Cada palabra buscada
# coincide con cualquiera de sus alternativas (sin tildes, en minúsculas).
SYNONYMS: dict[str, list[str]] = {
    "morosidad": ["morosidad", "cartera atrasada"],
    "moroso": ["morosidad", "cartera atrasada"],
    "dolar": ["dolar", "tipo de cambio"],
    "dolares": ["dolar", "tipo de cambio"],
    "inflacion": ["inflacion", "indice de precios", "ipc"],
    "pbi": ["pbi", "producto bruto interno"],
    "gdp": ["pbi", "producto bruto interno"],
    "desempleo": ["desempleo", "desocupa"],
    "reservas": ["reservas", "rin"],
    "prestamos": ["prestamos", "credito", "colocaciones"],
    "creditos": ["credito", "colocaciones"],
}


def _plain(word: str) -> str:
    """Minúsculas y sin tildes, para buscar en SYNONYMS."""
    import unicodedata

    decomposed = unicodedata.normalize("NFKD", word.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _conn(conn: PeruOpen | None) -> PeruOpen:
    if conn is not None:
        return conn
    from .. import _pe

    return _pe()


def _table_for(code: str, conn: PeruOpen) -> str:
    row = conn.query("SELECT table_name FROM bcrp_catalog WHERE code = ?", [code]).fetchone()
    if row is None:
        raise LookupError(
            f"La serie {code!r} no está en el catálogo del BCRP. "
            "Búscala con pe.macro.search('palabras clave')."
        )
    return str(row[0])


def series(
    code: str,
    start: DateLike = None,
    end: DateLike = None,
    *,
    conn: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Cualquier serie del BCRP por su código. Columnas: date, value."""
    c = _conn(conn)
    table = _table_for(code, c)
    sql = f"SELECT date, value FROM {table} WHERE code = ?"
    params: list[object] = [code]
    if start is not None:
        sql += " AND date >= CAST(? AS DATE)"
        params.append(str(start))
    if end is not None:
        sql += " AND date <= CAST(? AS DATE)"
        params.append(str(end))
    return c.query(sql + " ORDER BY date", params)


def search(
    text: str,
    *,
    frequency: Literal["daily", "monthly", "quarterly", "annual"] | None = None,
    active_only: bool = True,
    limit: int = 20,
    conn: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Busca series del BCRP por palabras (sin importar tildes ni mayúsculas).

    Todas las palabras deben aparecer en el nombre, la categoría o el grupo.
    Columnas: code, series_group, name, category, unit, frequency, last_date, table_name.
    """
    words = [w for w in text.lower().split() if w]
    if not words:
        raise ValueError("Escribe al menos una palabra para buscar")
    haystack = "lower(strip_accents(name || ' ' || category || ' ' || series_group))"
    conditions, params = [], []
    for word in words:
        alternatives = SYNONYMS.get(_plain(word), [word])
        conditions.append(
            "("
            + " OR ".join(
                f"{haystack} LIKE '%' || lower(strip_accents(?)) || '%'" for _ in alternatives
            )
            + ")"
        )
        params.extend(alternatives)
    sql = (
        "SELECT code, series_group, name, category, unit, frequency, last_date, table_name "
        "FROM bcrp_catalog WHERE " + " AND ".join(conditions)
    )
    if frequency is not None:
        sql += " AND frequency = ?"
        params.append(frequency)
    if active_only:
        sql += " AND is_active"
    sql += " ORDER BY is_active DESC, observations DESC, code LIMIT ?"
    params.append(int(limit))
    return _conn(conn).query(sql, params)


def exchange_rate(
    start: DateLike = None,
    end: DateLike = None,
    *,
    kind: Literal["interbank", "sbs"] = "interbank",
    side: Literal["buy", "sell"] = "sell",
    conn: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Tipo de cambio diario, en S/ por US$ (BCRP)."""
    try:
        code = EXCHANGE_RATE[(kind, side)]
    except KeyError:
        raise ValueError("kind debe ser 'interbank' o 'sbs', y side 'buy' o 'sell'") from None
    return series(code, start, end, conn=conn)


def inflation(
    start: DateLike = None,
    end: DateLike = None,
    *,
    period: Literal["12m", "monthly"] = "12m",
    conn: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Inflación de Lima Metropolitana en % (IPC, BCRP): variación en 12 meses o mensual."""
    if period not in INFLATION:
        raise ValueError("period debe ser '12m' o 'monthly'")
    return series(INFLATION[period], start, end, conn=conn)


def policy_rate(
    start: DateLike = None, end: DateLike = None, *, conn: PeruOpen | None = None
) -> duckdb.DuckDBPyRelation:
    """Tasa de referencia de la política monetaria del BCRP, en %."""
    return series(POLICY_RATE, start, end, conn=conn)


def gdp_growth(
    start: DateLike = None, end: DateLike = None, *, conn: PeruOpen | None = None
) -> duckdb.DuckDBPyRelation:
    """Crecimiento del PBI, variación % interanual (mensual, BCRP)."""
    return series(GDP_GROWTH, start, end, conn=conn)


def uit(year: int | None = None, *, conn: PeruOpen | None = None) -> int:
    """Valor de la UIT en soles para un año (por defecto, el actual)."""
    y = year or date.today().year
    row = _conn(conn).query("SELECT value FROM sunat_uit WHERE year = ?", [y]).fetchone()
    if row is None:
        raise LookupError(f"No hay valor de UIT para {y}")
    return int(row[0])


def uit_history(*, conn: PeruOpen | None = None) -> duckdb.DuckDBPyRelation:
    """Tabla completa de la UIT: year, value, legal_basis."""
    return _conn(conn).query("SELECT * FROM sunat_uit ORDER BY year")
