"""Motor de consultas: DuckDB sobre los Parquet de la caché.

Cada dataset aparece como una tabla (vista) con su nombre. Antes de ejecutar
un SQL se detecta qué datasets menciona y solo esos se descargan.
"""

from __future__ import annotations

import re
import threading
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from .config import load_settings
from .data_manager import DataManager
from .exceptions import PeruOpenError, ReadOnlyQueryError


class _UnknownTableError(ReadOnlyQueryError):
    """La consulta menciona una tabla que la etiqueta en caché no conoce."""


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_SQL_LENGTH = 10_000
DEFAULT_LIMIT = 100
MAX_LIMIT = 1_000
DEFAULT_TIMEOUT_S = 30.0


def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _view_sql(name: str, path: Path) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Nombre de dataset inválido: {name!r}")
    literal = path.as_posix().replace("'", "''")
    return f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{literal}')"


class PeruOpen:
    """Conexión a los datos de peruopen.

    conn = PeruOpen()                         # última snapshot
    conn = PeruOpen(snapshot="2026-11-22")    # fija una versión (reproducible)
    conn.query("SELECT * FROM macro_uit").df()
    """

    def __init__(
        self,
        *,
        snapshot: str | None = None,
        base_url: str | None = None,
        cache_dir: str | Path | None = None,
        offline: bool | None = None,
    ) -> None:
        self.settings = load_settings(base_url=base_url, cache_dir=cache_dir, offline=offline)
        self.data = DataManager(self.settings, snapshot=snapshot)
        self.con = duckdb.connect()
        self._views: dict[str, Path] = {}

    # -- catálogo -----------------------------------------------------------

    def list_datasets(self) -> list[dict[str, Any]]:
        manifest = self.data.manifest()
        return [
            {
                "dataset": name,
                "description": e["description"],
                "record_count": e["record_count"],
                "source_name": e["source_name"],
                "retrieved_at": e["retrieved_at"],
                "license": e["reuse_policy"].get("license"),
            }
            for name, e in sorted(manifest["datasets"].items())
        ]

    def describe(self, name: str) -> dict[str, Any]:
        entry = self.data.entry(name)
        keep = (
            "description", "module", "columns", "primary_key", "record_count", "source_name",
            "source_url", "retrieved_at", "update_frequency", "reuse_policy", "snapshot",
        )  # fmt: skip
        return {"dataset": name, **{k: entry.get(k) for k in keep}}

    def referenced(self, sql: str) -> list[str]:
        """Datasets que el SQL menciona (por nombre exacto de tabla)."""
        return [
            name
            for name in self.data.names()
            if re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", sql, flags=re.IGNORECASE)
        ]

    # -- consultas ----------------------------------------------------------

    def _register(self, names: list[str]) -> None:
        for name in names:
            path = self.data.ensure(name)
            if self._views.get(name) != path:
                self.con.execute(_view_sql(name, path))
                self._views[name] = path

    def query(
        self, sql: str, params: list[Any] | dict[str, Any] | None = None
    ) -> duckdb.DuckDBPyRelation:
        """Ejecuta SQL. Devuelve una relación de DuckDB: .df(), .pl(), .arrow() o .fetchall()."""
        self._register(self.referenced(sql))
        try:
            return self.con.sql(sql, params=params)
        except duckdb.CatalogException:
            # ¿Tabla desconocida? Puede ser un dataset nuevo que la etiqueta en
            # caché aún no conoce: se revisa la vitrina una vez y se reintenta.
            if not self._try_refresh():
                raise
            self._register(self.referenced(sql))
            return self.con.sql(sql, params=params)

    def _try_refresh(self) -> bool:
        """Relee la etiqueta de la vitrina si no se hizo ya en esta sesión."""
        if self.data.refreshed or self.data.snapshot or self.settings.offline:
            return False
        try:
            self.data.manifest(refresh=True)
        except PeruOpenError:
            return False
        return True

    def table(self, name: str) -> duckdb.DuckDBPyRelation:
        self.data.entry(name)  # error claro si no existe
        self._register([name])
        return self.con.table(name)

    def query_readonly(
        self,
        sql: str,
        *,
        limit: int = DEFAULT_LIMIT,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Consulta para agentes (MCP): solo un SELECT, sin acceso a archivos
        fuera de la caché, con límite de filas y timeout."""
        try:
            return self._query_readonly(sql, limit=limit, timeout_s=timeout_s)
        except _UnknownTableError:
            if not self._try_refresh():
                raise
            return self._query_readonly(sql, limit=limit, timeout_s=timeout_s)

    def _query_readonly(self, sql: str, *, limit: int, timeout_s: float) -> dict[str, Any]:
        cleaned = sql.strip().rstrip(";").strip()
        if not cleaned:
            raise ReadOnlyQueryError("La consulta está vacía.")
        if len(cleaned) > MAX_SQL_LENGTH:
            raise ReadOnlyQueryError(f"La consulta supera {MAX_SQL_LENGTH} caracteres.")
        try:
            statements = duckdb.extract_statements(cleaned)
        except duckdb.Error as exc:
            raise ReadOnlyQueryError(f"SQL inválido: {exc}") from exc
        if len(statements) != 1:
            raise ReadOnlyQueryError("Solo se permite una sentencia por consulta.")
        if statements[0].type != duckdb.StatementType.SELECT:
            raise ReadOnlyQueryError(
                f"Solo se permiten consultas SELECT (recibido: {statements[0].type.name})."
            )
        limit = max(1, min(int(limit), MAX_LIMIT))

        names = self.referenced(cleaned)
        paths = {name: self.data.ensure(name) for name in names}
        con = duckdb.connect()
        try:
            for name, path in paths.items():
                con.execute(_view_sql(name, path))
            # Solo los archivos exactos que usa la consulta. No se usa
            # allowed_directories porque en Windows, si el proceso hijo de una
            # app de la Microsoft Store (p. ej. Claude Desktop) escribió la caché,
            # la carpeta real está redirigida y DuckDB no reconoce el prefijo.
            if paths:
                files = ", ".join(_sql_literal(p.as_posix()) for p in paths.values())
                con.execute(f"SET allowed_paths=[{files}]")
            con.execute("SET enable_external_access=false")
            con.execute("SET lock_configuration=true")
            timer = threading.Timer(timeout_s, con.interrupt)
            timer.start()
            try:
                relation = con.sql(f"SELECT * FROM ({cleaned}) AS q LIMIT {limit + 1}")
                columns = list(relation.columns)
                rows = relation.fetchall()
            except duckdb.InterruptException as exc:
                raise ReadOnlyQueryError(
                    f"La consulta superó el límite de {timeout_s:.0f} s."
                ) from exc
            except duckdb.CatalogException as exc:
                raise _UnknownTableError(str(exc)) from exc
            except duckdb.Error as exc:
                raise ReadOnlyQueryError(str(exc)) from exc
            finally:
                timer.cancel()
        finally:
            con.close()

        truncated = len(rows) > limit
        rows = rows[:limit]
        return {
            "columns": columns,
            "rows": [{c: _jsonable(v) for c, v in zip(columns, row, strict=True)} for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
            "datasets": {n: self.data.entry(n)["snapshot"] for n in names},
        }

    # -- mantenimiento ------------------------------------------------------

    def update(self, names: list[str] | None = None) -> dict[str, str]:
        result = self.data.update(names)
        self._views.clear()
        return result

    def status(self) -> dict[str, Any]:
        return self.data.status()

    def clear_cache(self) -> None:
        self.con.close()
        self.data.clear_cache()
        self.con = duckdb.connect()
        self._views.clear()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.hex()
    return value
