from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipelines.common import sha256_file


def _entry(path: Path, table: pa.Table, description: str, primary_key: list[str]) -> dict[str, Any]:
    return {
        "file": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "record_count": table.num_rows,
        "description": description,
        "module": "macro",
        "columns": [{"name": f.name, "type": str(f.type), "description": ""} for f in table.schema],
        "primary_key": primary_key,
        "source_name": "prueba",
        "source_url": "https://example.org",
        "source_mode": "live",
        "source_last_modified": None,
        "retrieved_at": "2026-11-22T00:00:00+00:00",
        "update_frequency": "",
        "reuse_policy": {"license": "prueba"},
        "notes": [],
    }


def _write(out_dir: Path, name: str, table: pa.Table) -> Path:
    path = out_dir / f"{name}.parquet"
    pq.write_table(table, path, compression="zstd")
    return path


def bcrp_tables() -> dict[str, pa.Table]:
    """Un BCRP en miniatura: 2 series diarias y 1 mensual, con su catálogo."""
    catalog = pa.table(
        {
            "code": ["PD04637PD", "PD04638PD", "PN01273PM", "PN07746EM"],
            "description": [
                "Tipo de cambio interbancario, compra",
                "Tipo de cambio interbancario, venta",
                "Inflación anual: IPC Lima Metropolitana, variación % 12 meses",
                "Morosidad bancaria: cartera atrasada / colocaciones de las empresas bancarias",
            ],
            "name": [
                "Tipo de cambio - TC Interbancario (S/ por US$) - Compra",
                "Tipo de cambio - TC Interbancario (S/ por US$) - Venta",
                "Índice de precios Lima Metropolitana (var% 12 meses) - IPC",
                "Cartera atrasada neta / Colocaciones netas (%) - Empresas Bancarias",
            ],
            "unit": ["S/ por US$", "S/ por US$", "%", "%"],
            "frequency": ["daily", "daily", "monthly", "monthly"],
            "table_name": ["bcrp_daily", "bcrp_daily", "bcrp_monthly", "bcrp_monthly"],
            "first_date": [date(2026, 11, 18), date(2026, 11, 18), date(2026, 9, 1), None],
            "last_date": [date(2026, 11, 19), date(2026, 11, 19), date(2026, 10, 1), None],
            "observations": pa.array([2, 2, 2, 0], pa.int64()),
        }
    )
    daily = pa.table(
        {
            "code": ["PD04637PD", "PD04637PD", "PD04638PD", "PD04638PD"],
            "date": [date(2026, 11, 18), date(2026, 11, 19)] * 2,
            "value": [3.430, 3.439, 3.432, 3.441],
        }
    )
    monthly = pa.table(
        {
            "code": ["PN01273PM", "PN01273PM"],
            "date": [date(2026, 9, 1), date(2026, 10, 1)],
            "value": [4.55, 5.25],
        }
    )
    return {"bcrp_catalog": catalog, "bcrp_daily": daily, "bcrp_monthly": monthly}


def make_catalog(
    out_dir: Path, uit_rows: list[tuple[int, int, str]], *, with_bcrp: bool = False
) -> None:
    """Escribe un build mínimo (sin red) para probar la vitrina y la librería."""
    out_dir.mkdir(parents=True, exist_ok=True)
    uit = pa.table(
        {
            "year": pa.array([r[0] for r in uit_rows], pa.int16()),
            "value": pa.array([r[1] for r in uit_rows], pa.int32()),
            "legal_basis": [r[2] for r in uit_rows],
        }
    )
    datasets = {
        "sunat_uit": _entry(_write(out_dir, "sunat_uit", uit), uit, "UIT de prueba", ["year"])
    }
    if with_bcrp:
        for name, table in bcrp_tables().items():
            key = ["code"] if name == "bcrp_catalog" else ["code", "date"]
            datasets[name] = _entry(_write(out_dir, name, table), table, f"{name} de prueba", key)
    catalog = {"run_id": "test", "built_at": "", "datasets": datasets, "failed": {}}
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
