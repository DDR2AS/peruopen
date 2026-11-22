"""Publica `data/normalized/` en la vitrina (carpeta local o Cloudflare R2).

Layout:
    v1/manifest.json                          ← la "etiqueta": apunta a la última snapshot
    v1/snapshots/<id>/manifest.json           ← copia congelada, para fijar versiones
    v1/snapshots/<id>/<dataset>.parquet       ← inmutable, nunca se sobrescribe

Reglas:
- Si un dataset no cambió (mismo sha256), no se vuelve a subir: el manifest
  nuevo apunta al archivo de la snapshot anterior.
- Si un dataset falló en el build, se conserva su versión anterior.
- `v1/manifest.json` se reemplaza al final, después de subir y verificar todo,
  para que nadie vea nunca un manifest que apunte a archivos incompletos.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .build import CATALOG_NAME
from .common import NORMALIZED_DIR

log = logging.getLogger("peruopen.pipelines")

FORMAT_VERSION = 1
PREFIX = f"v{FORMAT_VERSION}"
LATEST_KEY = f"{PREFIX}/manifest.json"
IMMUTABLE = "public, max-age=31536000, immutable"
SHORT = "public, max-age=300"
PARQUET_TYPE = "application/vnd.apache.parquet"
JSON_TYPE = "application/json"


class Target(Protocol):
    def read(self, key: str) -> bytes | None: ...
    def exists(self, key: str) -> bool: ...
    def size(self, key: str) -> int | None: ...
    def put_file(self, key: str, path: Path, content_type: str, cache_control: str) -> None: ...
    def put_bytes(self, key: str, data: bytes, content_type: str, cache_control: str) -> None: ...


class LocalTarget:
    """Vitrina en una carpeta. Sirve para desarrollo y tests."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / key

    def read(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def size(self, key: str) -> int | None:
        path = self._path(key)
        return path.stat().st_size if path.exists() else None

    def put_file(self, key: str, path: Path, content_type: str, cache_control: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    def put_bytes(self, key: str, data: bytes, content_type: str, cache_control: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dest)

    def __str__(self) -> str:
        return f"carpeta local {self.root}"


class R2Target:
    """Vitrina en Cloudflare R2 (API compatible con S3).

    Credenciales por variables de entorno (nunca en el código):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY y R2_BUCKET.
    """

    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise SystemExit('Falta boto3: pip install -e ".[pipeline]"') from exc
        missing = [
            v
            for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
            if not os.environ.get(v)
        ]
        if missing:
            raise SystemExit(f"Faltan variables de entorno para R2: {', '.join(missing)}")
        self.bucket = os.environ.get("R2_BUCKET", "peruopen-data")
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    def _missing(self, exc: Exception) -> bool:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        return code in {"404", "NoSuchKey", "NotFound"}

    def read(self, key: str) -> bytes | None:
        try:
            body: bytes = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            return body
        except Exception as exc:
            if self._missing(exc):
                return None
            raise

    def size(self, key: str) -> int | None:
        try:
            length: int = self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
            return length
        except Exception as exc:
            if self._missing(exc):
                return None
            raise

    def exists(self, key: str) -> bool:
        return self.size(key) is not None

    def put_file(self, key: str, path: Path, content_type: str, cache_control: str) -> None:
        self.client.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type, "CacheControl": cache_control},
        )

    def put_bytes(self, key: str, data: bytes, content_type: str, cache_control: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl=cache_control,
        )

    def __str__(self) -> str:
        return f"R2 bucket {self.bucket}"


def _new_snapshot_id(target: Target, now: datetime) -> str:
    base = now.strftime("%Y-%m-%d")
    snapshot_id, n = base, 1
    while target.exists(f"{PREFIX}/snapshots/{snapshot_id}/manifest.json"):
        n += 1
        snapshot_id = f"{base}.{n}"
    return snapshot_id


def publish(
    target: Target,
    normalized_dir: Path = NORMALIZED_DIR,
    *,
    allow_fallback: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    catalog_path = normalized_dir / CATALOG_NAME
    if not catalog_path.exists():
        raise SystemExit(f"No existe {catalog_path}: corre primero `python -m pipelines build`")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not catalog["datasets"]:
        raise SystemExit("El build no produjo ningún dataset válido: no se publica nada")

    previous_raw = target.read(LATEST_KEY)
    previous = json.loads(previous_raw) if previous_raw else {"datasets": {}}
    snapshot_id = _new_snapshot_id(target, now)
    log.info("Publicando snapshot %s en %s", snapshot_id, target)

    datasets: dict[str, Any] = {}
    uploaded: dict[str, int] = {}
    for name, entry in catalog["datasets"].items():
        if entry["source_mode"] != "live" and not allow_fallback:
            raise SystemExit(f"{name} tiene source_mode={entry['source_mode']!r}: no se publica")
        meta = {k: v for k, v in entry.items() if k != "file"}
        prev = previous["datasets"].get(name)
        if prev and prev["sha256"] == entry["sha256"]:
            datasets[name] = {**meta, "path": prev["path"], "snapshot": prev["snapshot"]}
            log.info("  = %s sin cambios (se reutiliza %s)", name, prev["snapshot"])
            continue
        key = f"{PREFIX}/snapshots/{snapshot_id}/{name}.parquet"
        target.put_file(key, normalized_dir / entry["file"], PARQUET_TYPE, IMMUTABLE)
        uploaded[key] = entry["bytes"]
        datasets[name] = {**meta, "path": key, "snapshot": snapshot_id}
        log.info("  ↑ %s (%s bytes)", name, entry["bytes"])

    for name, prev in previous["datasets"].items():
        if name not in datasets:
            datasets[name] = prev
            reason = catalog.get("failed", {}).get(name, "no se construyó en este build")
            log.warning("  ! %s conserva la snapshot %s (%s)", name, prev["snapshot"], reason)

    for key, expected in uploaded.items():
        actual = target.size(key)
        if actual != expected:
            raise SystemExit(
                f"Verificación fallida en {key}: {actual} bytes, se esperaban {expected}"
            )

    manifest = {
        "format_version": FORMAT_VERSION,
        "snapshot": snapshot_id,
        "generated_at": now.isoformat(),
        "datasets": dict(sorted(datasets.items())),
    }
    data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    target.put_bytes(f"{PREFIX}/snapshots/{snapshot_id}/manifest.json", data, JSON_TYPE, IMMUTABLE)
    target.put_bytes(LATEST_KEY, data, JSON_TYPE, SHORT)
    log.info("Listo: %s apunta a la snapshot %s", LATEST_KEY, snapshot_id)
    return manifest
