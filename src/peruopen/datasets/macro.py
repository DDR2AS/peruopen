"""Atajos para los datos macroeconómicos (BCRP y UIT).

import peruopen as pe
pe.macro.tipo_cambio(desde="2026-01-01").df()
pe.macro.uit(2026)            # -> 5500
"""

from __future__ import annotations

from datetime import date
from typing import Literal

import duckdb

from ..engine import PeruOpen

TIPO_CAMBIO = {
    ("interbancario", "compra"): "PD04637PD",
    ("interbancario", "venta"): "PD04638PD",
    ("sbs", "compra"): "PD04639PD",
    ("sbs", "venta"): "PD04640PD",
}
INFLACION_MENSUAL = "PN01271PM"
INFLACION_12_MESES = "PN01273PM"
TASA_REFERENCIA = "PD04722MM"
PBI_VARIACION = "PN01728AM"


def _conn(pe: PeruOpen | None) -> PeruOpen:
    if pe is not None:
        return pe
    from .. import _pe

    return _pe()


def serie(
    codigo: str,
    desde: str | date | None = None,
    hasta: str | date | None = None,
    *,
    pe: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Una serie del BCRP por código, con columnas fecha y valor."""
    sql = "SELECT fecha, valor FROM macro_series WHERE serie = ?"
    params: list[object] = [codigo]
    if desde is not None:
        sql += " AND fecha >= CAST(? AS DATE)"
        params.append(str(desde))
    if hasta is not None:
        sql += " AND fecha <= CAST(? AS DATE)"
        params.append(str(hasta))
    return _conn(pe).query(sql + " ORDER BY fecha", params)


def tipo_cambio(
    desde: str | date | None = None,
    hasta: str | date | None = None,
    *,
    tipo: Literal["interbancario", "sbs"] = "interbancario",
    lado: Literal["compra", "venta"] = "venta",
    pe: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Tipo de cambio diario S/ por US$ (BCRP)."""
    try:
        codigo = TIPO_CAMBIO[(tipo, lado)]
    except KeyError:
        raise ValueError(
            "tipo debe ser 'interbancario' o 'sbs', y lado 'compra' o 'venta'"
        ) from None
    return serie(codigo, desde, hasta, pe=pe)


def inflacion(
    desde: str | date | None = None,
    hasta: str | date | None = None,
    *,
    periodo: Literal["mensual", "12_meses"] = "12_meses",
    pe: PeruOpen | None = None,
) -> duckdb.DuckDBPyRelation:
    """Inflación de Lima Metropolitana en % (IPC, BCRP)."""
    codigo = INFLACION_MENSUAL if periodo == "mensual" else INFLACION_12_MESES
    return serie(codigo, desde, hasta, pe=pe)


def uit(anio: int | None = None, *, pe: PeruOpen | None = None) -> int:
    """Valor de la UIT en soles para un año (por defecto, el actual)."""
    year = anio or date.today().year
    row = _conn(pe).query("SELECT valor FROM macro_uit WHERE anio = ?", [year]).fetchone()
    if row is None:
        raise LookupError(f"No hay valor de UIT para {year}")
    return int(row[0])


def uit_historica(*, pe: PeruOpen | None = None) -> duckdb.DuckDBPyRelation:
    """Tabla completa de la UIT: anio, valor, base_legal."""
    return _conn(pe).query("SELECT * FROM macro_uit ORDER BY anio")
