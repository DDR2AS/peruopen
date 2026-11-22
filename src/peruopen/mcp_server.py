"""Servidor MCP: expone los datos de peruopen a agentes de IA (Claude, Cursor…).

Cuatro tools, a propósito pocas, porque un agente ya sabe escribir SQL:
- list_datasets(): qué datasets hay.
- describe_dataset(dataset): columnas, fuente, licencia y fecha del dato.
- search_series(text): busca el código de una serie del BCRP.
- query(sql, limit): SQL de solo lectura (ver PeruOpen.query_readonly).

Configuración en Claude Desktop / Claude Code:

    {"mcpServers": {"peruopen": {
        "command": "uvx", "args": ["--from", "peruopen[mcp]", "peruopen-mcp"]}}}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import duckdb

from .engine import DEFAULT_LIMIT, MAX_LIMIT, PeruOpen, _jsonable
from .exceptions import PeruOpenError

FREQUENCIES = ("daily", "monthly")

INSTRUCTIONS = """\
Datos públicos oficiales del Perú (Peru official open data), curados y versionados.
Incluye los principales indicadores del BCRP: tipo de cambio / exchange rate,
inflación, tasa de referencia, PBI / GDP, reservas internacionales, desempleo de
Lima, morosidad bancaria, cobre y oro; y la UIT de SUNAT.

Flujo recomendado:
1. search_series("palabras en español") o una consulta a bcrp_catalog para
   encontrar el código de la serie y la tabla donde están sus datos.
2. describe_dataset para ver columnas, fuente y fecha del dato.
3. query con SQL (DuckDB). Las tablas se llaman igual que los datasets:
   bcrp_daily y bcrp_monthly (code, date, value), bcrp_catalog (descripción,
   unidad y frecuencia de cada serie) y sunat_uit (year, value, legal_basis).
Solo se permiten SELECT.
Cita siempre la fuente (source_name) y la fecha del dato (retrieved_at) al responder.
"""


def build_server(conn: PeruOpen | None = None) -> Any:
    try:
        from fastmcp import FastMCP
        from fastmcp.exceptions import ToolError
    except ImportError as exc:  # pragma: no cover
        raise SystemExit('El servidor MCP necesita el extra: pip install "peruopen[mcp]"') from exc

    db = conn or PeruOpen()
    mcp = FastMCP("peruopen", instructions=INSTRUCTIONS)

    def _call(fn: Callable[[], Any]) -> Any:
        # Los errores esperados (SQL rechazado, dataset inexistente, búsqueda
        # vacía…) vuelven al agente como un mensaje claro, sin traceback.
        try:
            return fn()
        except (PeruOpenError, ValueError, LookupError, duckdb.Error) as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    def list_datasets() -> list[dict[str, Any]]:
        """Lista los datasets disponibles con su descripción, fuente y fecha."""
        return _call(db.list_datasets)  # type: ignore[no-any-return]

    @mcp.tool
    def describe_dataset(dataset: str) -> dict[str, Any]:
        """Columnas (con descripción), clave primaria, fuente oficial, licencia y fecha del dato."""
        return _call(lambda: db.describe(dataset))  # type: ignore[no-any-return]

    @mcp.tool
    def search_series(text: str, frequency: str | None = None, limit: int = 20) -> dict[str, Any]:
        """Busca entre las series del BCRP disponibles por palabras en español, p. ej.
        "tipo de cambio", "morosidad" o "cobre". Devuelve code, description, name, unit,
        frequency, last_date y table_name (la tabla donde consultar sus datos).
        frequency es opcional: daily o monthly."""

        def run() -> dict[str, Any]:
            from .datasets import macro

            if frequency is not None and frequency not in FREQUENCIES:
                raise ValueError("frequency debe ser daily o monthly")
            rel = macro.search(
                text,
                frequency=frequency,  # type: ignore[arg-type]
                limit=max(1, min(limit, 100)),
                conn=db,
            )
            cols = list(rel.columns)
            rows = [dict(zip(cols, map(_jsonable, r), strict=True)) for r in rel.fetchall()]
            return {"results": rows, "count": len(rows)}

        return _call(run)  # type: ignore[no-any-return]

    @mcp.tool
    def query(sql: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Ejecuta un SELECT (DuckDB SQL) sobre los datasets. Las tablas se llaman igual que
        los datasets. Devuelve como máximo `limit` filas (tope 1000)."""
        return _call(lambda: db.query_readonly(sql, limit=min(limit, MAX_LIMIT)))  # type: ignore[no-any-return]

    return mcp


def main() -> None:
    # Sin el banner de FastMCP: los clientes MCP solo leen stdout, y el banner
    # (en stderr) ensucia los logs de Claude Desktop sin aportar nada.
    build_server().run(show_banner=False)


if __name__ == "__main__":
    main()
