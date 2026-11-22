"""Piezas compartidas por los extractores: HTTP robusto, snapshots crudos y
el resultado tipado de una extracción."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyarrow as pa

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
REGISTRY_PATH = DATA_DIR / "registry" / "datasets.json"

# Fase 0: el BCRP responde 403 al UA de httpx y datosabiertos.gob.pe responde
# 418 al de curl. Todos los extractores se presentan como un navegador.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class SourceError(RuntimeError):
    """La fuente oficial no respondió lo esperado tras varios intentos."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(
    url: str,
    *,
    what: str,
    validate: Callable[[bytes], bool],
    attempts: int = 4,
    timeout: float = 60.0,
    client: httpx.Client | None = None,
) -> httpx.Response:
    """GET con UA de navegador, validación del contenido y reintentos.

    `validate` recibe el cuerpo y dice si es lo esperado (p. ej. que un JSON
    empiece con `{`). Algunos WAF responden HTTP 200 con una página de
    verificación, así que el código HTTP no basta.
    """
    own_client = client is None
    http = client or httpx.Client(
        headers={"User-Agent": BROWSER_UA, "Accept-Language": "es-PE,es;q=0.9"},
        timeout=timeout,
        follow_redirects=True,
    )
    last_error = ""
    try:
        for attempt in range(attempts):
            try:
                response = http.get(url)
                if response.status_code == 200 and validate(response.content):
                    return response
                last_error = f"HTTP {response.status_code}, contenido: {response.content[:80]!r}"
            except httpx.HTTPError as exc:
                last_error = repr(exc)
            if attempt < attempts - 1:
                time.sleep(2**attempt)
    finally:
        if own_client:
            http.close()
    raise SourceError(f"{what}: falló tras {attempts} intentos ({last_error}) — {url}")


def write_raw(dataset: str, run_id: str, filename: str, content: bytes) -> Path:
    """Guarda la respuesta cruda de la fuente. Write-once: nunca se sobrescribe."""
    path = RAW_DIR / dataset / run_id / filename
    if path.exists():
        raise FileExistsError(f"El snapshot crudo ya existe y es write-once: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def new_run_id(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class ExtractionResult:
    """Lo que devuelve un extractor: la tabla y su procedencia."""

    dataset: str
    table: pa.Table
    source_url: str
    source_mode: str  # "live" | "fallback"
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_last_modified: str | None = None
    raw_files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
