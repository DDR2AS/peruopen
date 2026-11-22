"""extract → validate → Parquet. Escribe `data/normalized/` y su `catalog.json`.

Si un dataset falla, los demás se construyen igual y el fallo queda anotado en
el catálogo. Al publicar, ese dataset conserva su versión anterior.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .common import NORMALIZED_DIR, new_run_id, sha256_file
from .extractors import EXTRACTORS
from .registry import DatasetSpec, load_registry
from .validation import validate

log = logging.getLogger("peruopen.pipelines")

CATALOG_NAME = "catalog.json"


def build_dataset(spec: DatasetSpec, run_id: str, out_dir: Path) -> dict[str, Any]:
    result = EXTRACTORS[spec.extractor](spec, run_id)
    errors = validate(spec, result.table)
    if errors:
        raise ValueError("Validación fallida:\n- " + "\n- ".join(errors))
    path = out_dir / f"{spec.name}.parquet"
    pq.write_table(result.table, path, compression="zstd", row_group_size=100_000)
    return {
        "file": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "record_count": result.table.num_rows,
        "description": spec.description,
        "module": spec.module,
        "columns": [
            {"name": c.name, "type": c.type, "description": c.description} for c in spec.columns
        ],
        "primary_key": list(spec.primary_key),
        "source_name": spec.source_name,
        "source_url": spec.source_url,
        "source_mode": result.source_mode,
        "source_last_modified": result.source_last_modified,
        "retrieved_at": result.retrieved_at.isoformat(),
        "update_frequency": spec.update_frequency,
        "reuse_policy": spec.reuse_policy,
        "notes": result.notes,
    }


def build(only: list[str] | None = None, out_dir: Path = NORMALIZED_DIR) -> dict[str, Any]:
    registry = load_registry()
    unknown = set(only or []) - registry.keys()
    if unknown:
        raise SystemExit(
            f"Datasets desconocidos: {sorted(unknown)}. Disponibles: {sorted(registry)}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = new_run_id()
    catalog: dict[str, Any] = {
        "run_id": run_id,
        "built_at": datetime.now(UTC).isoformat(),
        "datasets": {},
        "failed": {},
    }
    for name, spec in registry.items():
        if only and name not in only:
            continue
        log.info("Construyendo %s…", name)
        try:
            catalog["datasets"][name] = build_dataset(spec, run_id, out_dir)
            log.info("  ✓ %s: %s filas", name, catalog["datasets"][name]["record_count"])
        except Exception as exc:  # un dataset roto no debe tumbar a los demás
            catalog["failed"][name] = f"{type(exc).__name__}: {exc}"
            log.error("  ✗ %s: %s", name, exc)
            log.debug(traceback.format_exc())
    (out_dir / CATALOG_NAME).write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return catalog
