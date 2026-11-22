"""Registro de datasets: `data/registry/datasets.json` es la fuente de verdad
(editada a mano) de qué datasets existen, su esquema y su licencia."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa

from .common import REGISTRY_PATH

ARROW_TYPES: dict[str, pa.DataType] = {
    "string": pa.string(),
    "date": pa.date32(),
    "float64": pa.float64(),
    "int16": pa.int16(),
    "int32": pa.int32(),
    "int64": pa.int64(),
    "bool": pa.bool_(),
}


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    description: str
    module: str
    extractor: str
    source_name: str
    source_url: str
    update_frequency: str
    primary_key: tuple[str, ...]
    min_records: int
    columns: tuple[Column, ...]
    reuse_policy: dict[str, Any]

    def arrow_schema(self) -> pa.Schema:
        return pa.schema([pa.field(c.name, ARROW_TYPES[c.type]) for c in self.columns])


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, DatasetSpec]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    specs = {}
    for name, entry in raw.items():
        specs[name] = DatasetSpec(
            name=name,
            description=entry["description"],
            module=entry["module"],
            extractor=entry["extractor"],
            source_name=entry["source_name"],
            source_url=entry["source_url"],
            update_frequency=entry["update_frequency"],
            primary_key=tuple(entry["primary_key"]),
            min_records=entry["min_records"],
            columns=tuple(Column(**c) for c in entry["columns"]),
            reuse_policy=entry["reuse_policy"],
        )
        unknown = {c.type for c in specs[name].columns} - ARROW_TYPES.keys()
        if unknown:
            raise ValueError(f"{name}: tipos de columna desconocidos {unknown}")
    return specs
