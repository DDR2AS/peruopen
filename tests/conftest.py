from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipelines.common import sha256_file


def make_catalog(out_dir: Path, uit_rows: list[tuple[int, int, str]]) -> None:
    """Escribe un build mínimo (sin red) para probar la vitrina y la librería."""
    out_dir.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "anio": pa.array([r[0] for r in uit_rows], pa.int16()),
            "valor": pa.array([r[1] for r in uit_rows], pa.int32()),
            "base_legal": [r[2] for r in uit_rows],
        }
    )
    path = out_dir / "macro_uit.parquet"
    pq.write_table(table, path, compression="zstd")
    entry = {
        "file": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "record_count": table.num_rows,
        "description": "UIT de prueba",
        "module": "macro",
        "columns": [
            {"name": "anio", "type": "int16", "description": ""},
            {"name": "valor", "type": "int32", "description": ""},
            {"name": "base_legal", "type": "string", "description": ""},
        ],
        "primary_key": ["anio"],
        "source_name": "SUNAT",
        "source_url": "https://www.sunat.gob.pe/indicestasas/uit.html",
        "source_mode": "live",
        "source_last_modified": None,
        "retrieved_at": "2026-11-22T00:00:00+00:00",
        "update_frequency": "Anual",
        "reuse_policy": {"license": "Dato normativo público"},
        "notes": [],
    }
    catalog = {"run_id": "test", "built_at": "", "datasets": {"macro_uit": entry}, "failed": {}}
    (out_dir / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")


@pytest.fixture
def uit_rows() -> list[tuple[int, int, str]]:
    return [(2025, 5350, "D.S. N° 260-2024-EF"), (2026, 5500, "D.S. N° 301-2025-EF")]


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "PERUOPEN_BASE_URL",
        "PERUOPEN_CACHE_DIR",
        "PERUOPEN_OFFLINE",
        "PERUOPEN_CHECK_HOURS",
    ):
        monkeypatch.delenv(var, raising=False)
