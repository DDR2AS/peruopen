"""Valor histórico de la UIT, desde la tabla oficial de SUNAT.

La página mezcla encodings (algunas filas en utf-8 y otras en latin-1) y
formatos de número ("5,500" y "3.100"), así que se parsea sobre bytes y solo
se extraen dígitos.
"""

from __future__ import annotations

import re

import pyarrow as pa

from ..common import ExtractionResult, fetch, write_raw
from ..registry import DatasetSpec

URL = "https://www.sunat.gob.pe/indicestasas/uit.html"

_TAGS = re.compile(rb"<[^>]+>")
_ENTITIES = re.compile(rb"&[a-zA-Z0-9#]+;")
_SPACES = re.compile(rb"\s+")
# "2026 5,500 D.S. N° 301-2025-EF"
_ROW = re.compile(
    rb"(?<!\d)((?:19|20)\d{2})\s+(\d{1,3}(?:[.,]\d{3})+|\d{3,6})\s+"
    rb"D\.\s*S\.\s*N\S{0,4}\s*(\d{1,4}-\d{2,4}-EF)",
    re.IGNORECASE,
)


# Antes de 1994 la tabla no es una serie anual limpia: 1993 tiene valores por
# semestre fijados por R.M. y en 1992 regía la URT, no la UIT.
MIN_YEAR = 1994


def parse_uit(html: bytes) -> list[tuple[int, int, str]]:
    """Devuelve [(anio, valor_soles, base_legal)] ordenado por año, desde 1994.

    Si un año aparece dos veces (1996 cambió en febrero), se queda la primera
    fila de la tabla, que es el valor vigente durante la mayor parte del año.
    """
    text = _SPACES.sub(b" ", _ENTITIES.sub(b" ", _TAGS.sub(b" ", html)))
    found: dict[int, tuple[int, str]] = {}
    for match in _ROW.finditer(text):
        year = int(match.group(1))
        if year < MIN_YEAR:
            continue
        value = int(re.sub(rb"[.,]", b"", match.group(2)))
        decree = "D.S. N° " + match.group(3).decode("ascii")
        found.setdefault(year, (value, decree))
    return [(year, *found[year]) for year in sorted(found)]


def extract(spec: DatasetSpec, run_id: str) -> ExtractionResult:
    response = fetch(URL, what="SUNAT UIT", validate=lambda b: b"UIT" in b.upper())
    raw = write_raw(spec.name, run_id, "uit.html", response.content)
    rows = parse_uit(response.content)
    if not rows:
        raise ValueError("No se encontraron filas de UIT en la página de SUNAT (¿cambió el HTML?)")
    table = pa.table(
        {
            "anio": [r[0] for r in rows],
            "valor": [r[1] for r in rows],
            "base_legal": [r[2] for r in rows],
        },
        schema=spec.arrow_schema(),
    )
    return ExtractionResult(
        dataset=spec.name,
        table=table,
        source_url=URL,
        source_mode="live",
        source_last_modified=response.headers.get("last-modified"),
        raw_files=[str(raw)],
        notes=[f"{len(rows)} años: {rows[0][0]} a {rows[-1][0]}"],
    )
