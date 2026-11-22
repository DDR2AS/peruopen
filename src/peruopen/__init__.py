"""peruopen: datos públicos oficiales del Perú, curados en Parquet.

    import peruopen as pe

    pe.list_datasets()
    pe.macro.exchange_rate(start="2026-01-01").df()
    pe.macro.search("morosidad bancaria").df()
    pe.query("SELECT * FROM sunat_uit ORDER BY year DESC LIMIT 5").df()

La primera vez descarga los datos que uses y los guarda en caché. Después
revisa como máximo una vez al día si hay una versión nueva.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("peruopen")
except PackageNotFoundError:  # ejecutando desde el código fuente sin instalar
    __version__ = "0.0.0+local"

from typing import Any

import duckdb

from .engine import PeruOpen
from .exceptions import (
    ConfigError,
    DatasetNotFoundError,
    DataUnavailableError,
    IntegrityError,
    PeruOpenError,
    ReadOnlyQueryError,
)

_default: PeruOpen | None = None


def _pe() -> PeruOpen:
    global _default
    if _default is None:
        _default = PeruOpen()
    return _default


def connect(
    *,
    snapshot: str | None = None,
    base_url: str | None = None,
    cache_dir: str | None = None,
    offline: bool | None = None,
) -> PeruOpen:
    """Crea una conexión propia. Usa `snapshot=` para fijar una versión de los datos."""
    return PeruOpen(snapshot=snapshot, base_url=base_url, cache_dir=cache_dir, offline=offline)


def query(sql: str, params: list[Any] | dict[str, Any] | None = None) -> duckdb.DuckDBPyRelation:
    """Ejecuta SQL sobre los datasets. Devuelve una relación: .df(), .pl(), .arrow()."""
    return _pe().query(sql, params)


def table(name: str) -> duckdb.DuckDBPyRelation:
    return _pe().table(name)


def list_datasets() -> list[dict[str, Any]]:
    return _pe().list_datasets()


def describe(name: str) -> dict[str, Any]:
    return _pe().describe(name)


def update(names: list[str] | None = None) -> dict[str, str]:
    """Revisa ahora si hay datos nuevos (sin esperar las 24 h) y los descarga."""
    return _pe().update(names)


def status() -> dict[str, Any]:
    """Qué snapshot tienes y qué datasets están en caché."""
    return _pe().status()


def clear_cache() -> None:
    _pe().clear_cache()


from .datasets import macro  # noqa: E402

__all__ = [
    "ConfigError",
    "DataUnavailableError",
    "DatasetNotFoundError",
    "IntegrityError",
    "PeruOpen",
    "PeruOpenError",
    "ReadOnlyQueryError",
    "__version__",
    "clear_cache",
    "connect",
    "describe",
    "list_datasets",
    "macro",
    "query",
    "status",
    "table",
    "update",
]
