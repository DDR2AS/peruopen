"""El modo solo lectura del MCP no debe permitir escribir ni leer archivos ajenos."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import peruopen
from peruopen import PeruOpen, ReadOnlyQueryError
from pipelines.publish import LocalTarget, publish
from tests.conftest import make_catalog


@pytest.fixture
def po(tmp_path: Path, uit_rows: list[tuple[int, int, str]]) -> PeruOpen:
    make_catalog(tmp_path / "normalized", uit_rows)
    publish(LocalTarget(tmp_path / "vitrina"), tmp_path / "normalized")
    return peruopen.connect(base_url=str(tmp_path / "vitrina"), cache_dir=str(tmp_path / "cache"))


def test_select_works_and_is_limited(po: PeruOpen) -> None:
    result = po.query_readonly("SELECT anio, valor FROM macro_uit ORDER BY anio", limit=1)
    assert result["columns"] == ["anio", "valor"]
    assert result["rows"] == [{"anio": 2025, "valor": 5350}]
    assert result["truncated"] is True
    assert result["datasets"] == {"macro_uit": result["datasets"]["macro_uit"]}


def test_with_clause_is_allowed(po: PeruOpen) -> None:
    sql = "WITH u AS (SELECT * FROM macro_uit) SELECT max(valor) AS m FROM u;"
    assert po.query_readonly(sql)["rows"] == [{"m": 5500}]


@pytest.mark.parametrize(
    "sql",
    [
        "DROP VIEW macro_uit",
        "CREATE TABLE x AS SELECT 1",
        "INSERT INTO macro_uit VALUES (1, 1, 'x')",
        "COPY (SELECT 1) TO 'x.csv'",
        "SET enable_external_access = true",
        "ATTACH 'otra.db'",
        "PRAGMA version",
        "SELECT 1; SELECT 2",
        "",
    ],
)
def test_non_select_is_rejected(po: PeruOpen, sql: str) -> None:
    with pytest.raises(ReadOnlyQueryError):
        po.query_readonly(sql)


def test_cannot_read_arbitrary_files(po: PeruOpen, tmp_path: Path) -> None:
    secret = tmp_path / "secreto.csv"
    secret.write_text("clave\nhunter2\n")
    for fn in ("read_csv", "read_text"):
        with pytest.raises(ReadOnlyQueryError):
            po.query_readonly(f"SELECT * FROM {fn}('{secret.as_posix()}')")


def test_mcp_server_tools(po: PeruOpen) -> None:
    fastmcp = pytest.importorskip("fastmcp")
    from peruopen.mcp_server import build_server

    async def run() -> None:
        async with fastmcp.Client(build_server(po)) as client:
            tools = {t.name for t in await client.list_tools()}
            assert tools == {"list_datasets", "describe_dataset", "query"}
            result = await client.call_tool("query", {"sql": "SELECT count(*) AS n FROM macro_uit"})
            assert result.data["rows"] == [{"n": 2}]

    asyncio.run(run())
