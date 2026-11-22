"""peruopen: datos públicos oficiales del Perú, curados en Parquet.

    import peruopen as po

    po.query("SELECT * FROM macro_uit ORDER BY anio DESC LIMIT 5").df()
    po.macro.tipo_cambio(desde="2026-01-01").pl()
    po.list_datasets()

La primera vez descarga los datos que uses y los guarda en caché. Después
revisa como máximo una vez al día si hay una versión nueva.
"""

from __future__ import annotations

__version__ = "0.1.0.dev0"

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


def _po() -> PeruOpen:
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
    return _po().query(sql, params)


def table(name: str) -> duckdb.DuckDBPyRelation:
    return _po().table(name)


def list_datasets() -> list[dict[str, Any]]:
    return _po().list_datasets()


def describe(name: str) -> dict[str, Any]:
    return _po().describe(name)


def update(names: list[str] | None = None) -> dict[str, str]:
    """Revisa ahora si hay datos nuevos (sin esperar las 24 h) y los descarga."""
    return _po().update(names)


def status() -> dict[str, Any]:
    """Qué snapshot tienes y qué datasets están en caché."""
    return _po().status()


def clear_cache() -> None:
    _po().clear_cache()


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
