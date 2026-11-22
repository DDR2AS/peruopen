"""Atajos de pe.macro sobre un BCRP en miniatura (sin red)."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

import pytest

import peruopen
from peruopen import PeruOpen
from pipelines.publish import LocalTarget, publish
from tests.conftest import make_catalog


@pytest.fixture
def pe(tmp_path: Path, uit_rows: list[tuple[int, int, str]]) -> PeruOpen:
    make_catalog(tmp_path / "normalized", uit_rows, with_bcrp=True)
    publish(LocalTarget(tmp_path / "vitrina"), tmp_path / "normalized", registry_names=set())
    return peruopen.connect(base_url=str(tmp_path / "vitrina"), cache_dir=str(tmp_path / "cache"))


def test_exchange_rate(pe: PeruOpen) -> None:
    rows = peruopen.macro.exchange_rate(conn=pe).fetchall()
    assert rows == [(date(2026, 11, 18), 3.432), (date(2026, 11, 19), 3.441)]
    buy = peruopen.macro.exchange_rate(start="2026-11-19", side="buy", conn=pe).fetchall()
    assert buy == [(date(2026, 11, 19), 3.439)]
    with pytest.raises(ValueError):
        peruopen.macro.exchange_rate(kind="paralelo", conn=pe)  # type: ignore[arg-type]


def test_series_routes_to_the_right_table(pe: PeruOpen) -> None:
    assert peruopen.macro.inflation(conn=pe).fetchall()[-1] == (date(2026, 10, 1), 5.25)
    assert peruopen.macro.series("PN01273PM", end="2026-09-30", conn=pe).fetchall() == [
        (date(2026, 9, 1), 4.55)
    ]
    with pytest.raises(LookupError, match="catalog"):
        peruopen.macro.series("NOEXISTE", conn=pe)


def test_only_needed_tables_are_downloaded(pe: PeruOpen) -> None:
    peruopen.macro.exchange_rate(conn=pe).fetchall()
    cached = {d["dataset"] for d in pe.status()["datasets"] if d["cached"]}
    assert cached == {"bcrp_catalog", "bcrp_daily"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("tipo de cambio venta", ["PD04638PD"]),
        ("INDICE precios", ["PN01273PM"]),  # sin tildes y en mayúsculas
        ("interbancario", ["PD04637PD", "PD04638PD"]),
        ("morosidad bancaria", ["PN07746EM"]),  # sinónimo: el BCRP dice "cartera atrasada"
        ("Inflación", ["PN01273PM"]),  # sinónimo: IPC / índice de precios
        ("no existe esto", []),
    ],
)
def test_search(pe: PeruOpen, text: str, expected: list[str]) -> None:
    codes = sorted(r[0] for r in peruopen.macro.search(text, conn=pe).fetchall())
    assert codes == expected


def test_search_by_frequency(pe: PeruOpen) -> None:
    rows = peruopen.macro.search("ipc", frequency="daily", conn=pe).fetchall()
    assert rows == []


def test_catalog_lists_available_series(pe: PeruOpen) -> None:
    codes = [r[0] for r in peruopen.macro.catalog(conn=pe).fetchall()]
    assert codes == ["PD04637PD", "PD04638PD", "PN01273PM", "PN07746EM"]


def test_uit(pe: PeruOpen) -> None:
    assert peruopen.macro.uit(2026, conn=pe) == 5500
    assert peruopen.macro.uit_history(conn=pe).columns == ["year", "value", "legal_basis"]
    with pytest.raises(LookupError):
        peruopen.macro.uit(1900, conn=pe)


def test_mcp_search_series(pe: PeruOpen) -> None:
    fastmcp = pytest.importorskip("fastmcp")
    from peruopen.mcp_server import build_server

    async def run() -> None:
        async with fastmcp.Client(build_server(pe)) as client:
            tools = {t.name for t in await client.list_tools()}
            assert "search_series" in tools
            result = await client.call_tool("search_series", {"text": "tipo de cambio venta"})
            assert [r["code"] for r in result.data["results"]] == ["PD04638PD"]
            assert result.data["results"][0]["last_date"] == "2026-11-19"

    asyncio.run(run())
