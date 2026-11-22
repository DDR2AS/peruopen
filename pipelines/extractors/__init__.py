"""Un extractor por fuente. Cada uno expone `extract(spec, run_id) -> ExtractionResult`."""

from __future__ import annotations

from collections.abc import Callable

from ..common import ExtractionResult
from ..registry import DatasetSpec
from . import bcrp, uit

Extractor = Callable[[DatasetSpec, str], ExtractionResult]

EXTRACTORS: dict[str, Extractor] = {
    "bcrp_catalog": bcrp.extract_catalog,
    "bcrp_data": bcrp.extract_data,
    "uit": uit.extract,
}
