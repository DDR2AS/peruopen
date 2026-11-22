"""Servidor MCP: expone los datos de peruopen a agentes de IA (Claude, Cursor…).

Tres tools, a propósito pocas, porque un agente ya sabe escribir SQL:
- list_datasets(): qué datasets hay.
- describe_dataset(dataset): columnas, fuente, licencia y fecha del dato.
- query(sql, limit): SQL de solo lectura (ver PeruOpen.query_readonly).

Configuración en Claude Desktop / Claude Code:

    {"mcpServers": {"peruopen": {
        "command": "uvx", "args": ["--from", "peruopen[mcp]", "peruopen-mcp"]}}}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .engine import DEFAULT_LIMIT, MAX_LIMIT, PeruOpen
from .exceptions import PeruOpenError

INSTRUCTIONS = """\
Datos públicos oficiales del Perú (BCRP, SUNAT, INEI…), curados y versionados.
Flujo recomendado: list_datasets → describe_dataset → query.
Cada dataset es una tabla con su mismo nombre. Solo se permiten SELECT.
Cita siempre la fuente (source_name) y la fecha del dato (retrieved_at) al responder.
"""


def build_server(pe: PeruOpen | None = None) -> Any:
    try:
        from fastmcp import FastMCP
        from fastmcp.exceptions import ToolError
    except ImportError as exc:  # pragma: no cover
        raise SystemExit('El servidor MCP necesita el extra: pip install "peruopen[mcp]"') from exc

    conn = pe or PeruOpen()
    mcp = FastMCP("peruopen", instructions=INSTRUCTIONS)

    def _call(fn: Callable[[], Any]) -> Any:
        # Los errores esperados (SQL rechazado, dataset inexistente…) vuelven al
        # agente como un mensaje claro, sin traceback.
        try:
            return fn()
        except PeruOpenError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool
    def list_datasets() -> list[dict[str, Any]]:
        """Lista los datasets disponibles con su descripción, fuente y fecha."""
        return _call(conn.list_datasets)  # type: ignore[no-any-return]

    @mcp.tool
    def describe_dataset(dataset: str) -> dict[str, Any]:
        """Columnas (con descripción), clave primaria, fuente oficial, licencia y fecha del dato."""
        return _call(lambda: conn.describe(dataset))  # type: ignore[no-any-return]

    @mcp.tool
    def query(sql: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Ejecuta un SELECT (DuckDB SQL) sobre los datasets. Las tablas se llaman igual que
        los datasets. Devuelve como máximo `limit` filas (tope 1000)."""
        return _call(lambda: conn.query_readonly(sql, limit=min(limit, MAX_LIMIT)))  # type: ignore[no-any-return]

    return mcp


def main() -> None:
    # Sin el banner de FastMCP: los clientes MCP solo leen stdout, y el banner
    # (en stderr) ensucia los logs de Claude Desktop sin aportar nada.
    build_server().run(show_banner=False)


if __name__ == "__main__":
    main()
