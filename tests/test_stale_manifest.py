"""Si la etiqueta en caché no conoce un dataset nuevo, la librería la relee.

Caso real: al actualizar peruopen, la etiqueta cacheada (vigente 24 h) aún no
listaba bcrp_catalog, y el servidor MCP fallaba con "Table … does not exist".
"""

from __future__ import annotations

from pathlib import Path

import pytest

import peruopen
from peruopen import data_manager
from pipelines.publish import LocalTarget, publish
from tests.conftest import make_catalog


@pytest.fixture
def vitrina(tmp_path: Path, uit_rows: list[tuple[int, int, str]]) -> Path:
    make_catalog(tmp_path / "normalized", uit_rows)  # solo sunat_uit
    publish(LocalTarget(tmp_path / "vitrina"), tmp_path / "normalized", registry_names=set())
    return tmp_path / "vitrina"


def _publish_with_bcrp(tmp_path: Path, uit_rows: list[tuple[int, int, str]], vitrina: Path) -> None:
    make_catalog(tmp_path / "normalized", uit_rows, with_bcrp=True)
    publish(LocalTarget(vitrina), tmp_path / "normalized", registry_names=set())


def test_query_refreshes_stale_manifest(
    tmp_path: Path, vitrina: Path, uit_rows: list[tuple[int, int, str]]
) -> None:
    cache = str(tmp_path / "cache")
    peruopen.connect(
        base_url=str(vitrina), cache_dir=cache
    ).list_datasets()  # cachea etiqueta vieja
    _publish_with_bcrp(tmp_path, uit_rows, vitrina)

    pe = peruopen.connect(base_url=str(vitrina), cache_dir=cache)  # etiqueta "fresca" (< 24 h)
    assert "bcrp_catalog" not in pe.data.names()
    assert pe.query("SELECT count(*) FROM bcrp_catalog").fetchone() == (4,)
    assert peruopen.macro.exchange_rate(conn=pe).fetchall()[-1][1] == 3.441


def test_readonly_query_refreshes_stale_manifest(
    tmp_path: Path, vitrina: Path, uit_rows: list[tuple[int, int, str]]
) -> None:
    cache = str(tmp_path / "cache")
    peruopen.connect(base_url=str(vitrina), cache_dir=cache).list_datasets()
    _publish_with_bcrp(tmp_path, uit_rows, vitrina)

    pe = peruopen.connect(base_url=str(vitrina), cache_dir=cache)
    result = pe.query_readonly("SELECT count(*) AS n FROM bcrp_daily")
    assert result["rows"] == [{"n": 4}]


def test_library_upgrade_invalidates_cached_manifest(
    tmp_path: Path,
    vitrina: Path,
    uit_rows: list[tuple[int, int, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = str(tmp_path / "cache")
    peruopen.connect(base_url=str(vitrina), cache_dir=cache).list_datasets()
    _publish_with_bcrp(tmp_path, uit_rows, vitrina)

    monkeypatch.setattr(data_manager, "__version__", "9.9.9")  # simula pip install -U
    pe = peruopen.connect(base_url=str(vitrina), cache_dir=cache)
    assert "bcrp_catalog" in pe.data.names()


def test_unknown_table_still_fails_clearly(tmp_path: Path, vitrina: Path) -> None:
    pe = peruopen.connect(base_url=str(vitrina), cache_dir=str(tmp_path / "cache"))
    with pytest.raises(peruopen.ReadOnlyQueryError, match="no_existe"):
        pe.query_readonly("SELECT * FROM no_existe")
