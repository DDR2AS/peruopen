"""Ciclo completo sin red: build falso → vitrina local → librería."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import peruopen
from peruopen import DatasetNotFoundError, DataUnavailableError, IntegrityError, PeruOpen
from pipelines.publish import LATEST_KEY, LocalTarget, publish
from tests.conftest import make_catalog

T1 = datetime(2026, 11, 23, tzinfo=UTC)
T2 = datetime(2026, 11, 30, tzinfo=UTC)


@pytest.fixture
def vitrina(tmp_path: Path, uit_rows: list[tuple[int, int, str]]) -> Path:
    make_catalog(tmp_path / "normalized", uit_rows)
    publish(LocalTarget(tmp_path / "vitrina"), tmp_path / "normalized", now=T1)
    return tmp_path / "vitrina"


def connect(vitrina: Path, tmp_path: Path, **kw: object) -> PeruOpen:
    return peruopen.connect(base_url=str(vitrina), cache_dir=str(tmp_path / "cache"), **kw)  # type: ignore[arg-type]


def test_publish_writes_manifest_and_snapshot(vitrina: Path) -> None:
    manifest = json.loads((vitrina / LATEST_KEY).read_text(encoding="utf-8"))
    assert manifest["snapshot"] == "2026-11-23"
    entry = manifest["datasets"]["sunat_uit"]
    assert entry["path"] == "v1/snapshots/2026-11-23/sunat_uit.parquet"
    assert (vitrina / entry["path"]).exists()
    assert (vitrina / "v1/snapshots/2026-11-23/manifest.json").exists()


def test_query_downloads_and_caches(vitrina: Path, tmp_path: Path) -> None:
    pe = connect(vitrina, tmp_path)
    assert pe.query("SELECT value FROM sunat_uit WHERE year = 2026").fetchone() == (5500,)
    assert peruopen.macro.uit(2025, conn=pe) == 5350
    status = pe.status()
    assert status["snapshot"] == "2026-11-23"
    assert status["datasets"][0]["cached"] is True


def test_unchanged_dataset_is_not_reuploaded(vitrina: Path, tmp_path: Path) -> None:
    manifest = publish(LocalTarget(vitrina), tmp_path / "normalized", now=T2)
    assert manifest["snapshot"] == "2026-11-30"
    assert manifest["datasets"]["sunat_uit"]["snapshot"] == "2026-11-23"
    assert not (vitrina / "v1/snapshots/2026-11-30/sunat_uit.parquet").exists()


def test_same_day_publish_gets_new_snapshot_id(vitrina: Path, tmp_path: Path) -> None:
    assert (
        publish(LocalTarget(vitrina), tmp_path / "normalized", now=T1)["snapshot"] == "2026-11-23.2"
    )


def test_new_data_is_picked_up_after_update(
    vitrina: Path, tmp_path: Path, uit_rows: list[tuple[int, int, str]]
) -> None:
    pe = connect(vitrina, tmp_path)
    assert pe.query("SELECT count(*) FROM sunat_uit").fetchone() == (2,)

    make_catalog(tmp_path / "normalized", [*uit_rows, (2027, 5700, "D.S. N° 999-2026-EF")])
    publish(LocalTarget(vitrina), tmp_path / "normalized", now=T2)

    # Dentro de las 24 h la librería no vuelve a mirar la vitrina…
    assert pe.query("SELECT count(*) FROM sunat_uit").fetchone() == (2,)
    # …salvo que se pida explícitamente.
    assert pe.update() == {"sunat_uit": "2026-11-30"}
    assert pe.query("SELECT count(*) FROM sunat_uit").fetchone() == (3,)


def test_snapshot_pinning_is_reproducible(
    vitrina: Path, tmp_path: Path, uit_rows: list[tuple[int, int, str]]
) -> None:
    make_catalog(tmp_path / "normalized", [*uit_rows, (2027, 5700, "D.S. N° 999-2026-EF")])
    publish(LocalTarget(vitrina), tmp_path / "normalized", now=T2)
    old = connect(vitrina, tmp_path, snapshot="2026-11-23")
    new = connect(vitrina, tmp_path)
    assert old.query("SELECT count(*) FROM sunat_uit").fetchone() == (2,)
    assert new.query("SELECT count(*) FROM sunat_uit").fetchone() == (3,)


def test_offline_uses_cache_and_fails_clearly_without_it(vitrina: Path, tmp_path: Path) -> None:
    with pytest.raises(DataUnavailableError, match="offline"):
        connect(vitrina, tmp_path, offline=True).list_datasets()
    connect(vitrina, tmp_path).query("SELECT * FROM sunat_uit").fetchall()
    offline = connect(vitrina, tmp_path, offline=True)
    assert offline.query("SELECT count(*) FROM sunat_uit").fetchone() == (2,)


def test_falls_back_to_cache_when_vitrina_is_down(
    vitrina: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connect(vitrina, tmp_path).query("SELECT * FROM sunat_uit").fetchall()
    monkeypatch.setenv("PERUOPEN_CHECK_HOURS", "0")  # obliga a revisar la vitrina
    gone = connect(tmp_path / "no-existe", tmp_path)
    with pytest.warns(UserWarning, match="caché"):
        assert gone.query("SELECT count(*) FROM sunat_uit").fetchone() == (2,)


def test_corrupted_file_is_rejected(vitrina: Path, tmp_path: Path) -> None:
    parquet = vitrina / "v1/snapshots/2026-11-23/sunat_uit.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"basura")
    with pytest.raises(IntegrityError):
        connect(vitrina, tmp_path).query("SELECT * FROM sunat_uit")
    assert not list((tmp_path / "cache" / "objects").glob("*"))


def test_unknown_dataset_suggests_name(vitrina: Path, tmp_path: Path) -> None:
    with pytest.raises(DatasetNotFoundError, match="sunat_uit"):
        connect(vitrina, tmp_path).describe("sunat_uits")


def test_missing_config_explains_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("peruopen.config.DEFAULT_BASE_URL", None)
    with pytest.raises(peruopen.ConfigError, match="PERUOPEN_BASE_URL"):
        peruopen.PeruOpen()
