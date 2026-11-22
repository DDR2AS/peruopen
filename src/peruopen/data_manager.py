"""Trae los datos de la vitrina a la caché local.

1. Lee la "etiqueta" (`v1/manifest.json`), como máximo una vez cada
   `check_interval` (24 h por defecto).
2. Descarga solo los datasets que se usan y que no están ya en caché.
3. Verifica el sha256 de cada archivo.

Los Parquet se guardan por su sha256 (`objects/<sha>.parquet`): si un dataset
no cambia entre snapshots, no se vuelve a descargar.

Sin red: usa la caché y avisa. Solo falla si nunca se descargó nada.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import time
import warnings
from pathlib import Path
from typing import Any

import httpx

from . import __version__
from .config import Settings
from .exceptions import DatasetNotFoundError, DataUnavailableError, IntegrityError

FORMAT_VERSION = 1
PREFIX = f"v{FORMAT_VERSION}"
USER_AGENT = f"peruopen/{__version__} (+https://github.com/DDR2AS/peruopen)"


class DataManager:
    def __init__(self, settings: Settings, snapshot: str | None = None) -> None:
        self.settings = settings
        self.snapshot = snapshot
        self.cache_dir = settings.cache_dir
        self.objects_dir = self.cache_dir / "objects"
        self._manifest: dict[str, Any] | None = None
        # True cuando la etiqueta se leyó de la vitrina en esta sesión (no de la caché).
        self.refreshed = False

    # -- acceso a la vitrina (http/https o carpeta local) -------------------

    def _is_http(self) -> bool:
        return self.settings.base_url.startswith(("http://", "https://"))

    def _local_root(self) -> Path:
        base = self.settings.base_url
        return Path(base[len("file://") :] if base.startswith("file://") else base)

    def _url(self, key: str) -> str:
        return self.settings.base_url.rstrip("/") + "/" + key

    def _read(self, key: str) -> bytes:
        if self._is_http():
            response = httpx.get(
                self._url(key),
                headers={"User-Agent": USER_AGENT},
                timeout=30.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.content
        return (self._local_root() / key).read_bytes()

    def _download(self, key: str, dest: Path, expected_sha: str) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".partial")
        digest = hashlib.sha256()
        try:
            with tmp.open("wb") as out:
                if self._is_http():
                    with httpx.stream(
                        "GET",
                        self._url(key),
                        headers={"User-Agent": USER_AGENT},
                        timeout=httpx.Timeout(30.0, read=300.0),
                        follow_redirects=True,
                    ) as response:
                        response.raise_for_status()
                        for chunk in response.iter_bytes(1 << 20):
                            digest.update(chunk)
                            out.write(chunk)
                else:
                    with (self._local_root() / key).open("rb") as src:
                        for chunk in iter(lambda: src.read(1 << 20), b""):
                            digest.update(chunk)
                            out.write(chunk)
            if digest.hexdigest() != expected_sha:
                raise IntegrityError(
                    f"El archivo {key} no coincide con su sha256 "
                    f"(esperado {expected_sha[:12]}…, obtenido {digest.hexdigest()[:12]}…)"
                )
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)

    # -- manifest -----------------------------------------------------------

    def _validate_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        if manifest.get("format_version") != FORMAT_VERSION:
            raise DataUnavailableError(
                f"La vitrina usa el formato {manifest.get('format_version')} y esta versión de "
                f"peruopen entiende el {FORMAT_VERSION}. Actualiza: pip install -U peruopen"
            )
        return manifest

    def _latest_manifest(self, refresh: bool) -> dict[str, Any]:
        cached = self.cache_dir / "manifest.json"
        checked = self.cache_dir / "manifest.checked"
        # "<timestamp> <versión de peruopen>": si la librería se actualizó, la
        # etiqueta en caché puede no conocer datasets nuevos, así que se revisa.
        stamp, _, version = checked.read_text().partition(" ") if checked.exists() else ("", "", "")
        try:
            age = time.time() - float(stamp)
        except ValueError:
            age = float("inf")
        fresh = age < self.settings.check_interval.total_seconds() and version == __version__

        if cached.exists() and (self.settings.offline or (fresh and not refresh)):
            return json.loads(cached.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        if self.settings.offline:
            raise DataUnavailableError(
                "Modo offline (PERUOPEN_OFFLINE) y todavía no hay datos en caché. "
                "Conéctate una vez para descargarlos."
            )
        try:
            manifest = self._validate_manifest(json.loads(self._read(f"{PREFIX}/manifest.json")))
        except (httpx.HTTPError, OSError, ValueError) as exc:
            if cached.exists():
                warnings.warn(
                    f"No se pudo revisar si hay datos nuevos ({exc}). "
                    "Se usan los datos que ya están en caché.",
                    stacklevel=4,
                )
                return json.loads(cached.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
            raise DataUnavailableError(
                f"No se pudo leer la vitrina ({self.settings.base_url}) y no hay caché: {exc}"
            ) from exc
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_name("manifest.json.tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, cached)
        checked.write_text(f"{time.time()} {__version__}")
        self.refreshed = True
        return manifest

    def _snapshot_manifest(self, snapshot: str) -> dict[str, Any]:
        cached = self.cache_dir / "snapshots" / snapshot / "manifest.json"
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        if self.settings.offline:
            raise DataUnavailableError(f"Modo offline y la snapshot {snapshot} no está en caché.")
        try:
            raw = self._read(f"{PREFIX}/snapshots/{snapshot}/manifest.json")
        except (httpx.HTTPError, OSError) as exc:
            raise DataUnavailableError(
                f"No existe o no se pudo leer la snapshot {snapshot!r}: {exc}"
            ) from exc
        manifest = self._validate_manifest(json.loads(raw))
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return manifest

    def manifest(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._manifest is None or refresh:
            self._manifest = (
                self._snapshot_manifest(self.snapshot)
                if self.snapshot
                else self._latest_manifest(refresh)
            )
        return self._manifest

    # -- datasets -----------------------------------------------------------

    def names(self) -> list[str]:
        return sorted(self.manifest()["datasets"])

    def entry(self, name: str) -> dict[str, Any]:
        datasets = self.manifest()["datasets"]
        if name not in datasets:
            close = difflib.get_close_matches(name, datasets, n=1)
            hint = f" ¿Quisiste decir {close[0]!r}?" if close else ""
            raise DatasetNotFoundError(
                f"No existe el dataset {name!r}.{hint} Disponibles: {', '.join(sorted(datasets))}"
            )
        return datasets[name]  # type: ignore[no-any-return]

    def object_path(self, entry: dict[str, Any]) -> Path:
        return self.objects_dir / f"{entry['sha256']}.parquet"

    def is_cached(self, name: str) -> bool:
        return self.object_path(self.entry(name)).exists()

    def ensure(self, name: str) -> Path:
        """Devuelve la ruta local del Parquet, descargándolo si hace falta."""
        entry = self.entry(name)
        path = self.object_path(entry)
        if not path.exists():
            if self.settings.offline:
                raise DataUnavailableError(f"Modo offline y {name!r} no está en caché.")
            try:
                self._download(entry["path"], path, entry["sha256"])
            except (httpx.HTTPError, OSError) as exc:
                raise DataUnavailableError(f"No se pudo descargar {name!r}: {exc}") from exc
            self._remember(name)
        return path

    def _remember(self, name: str) -> None:
        used_path = self.cache_dir / "used.json"
        used = set(json.loads(used_path.read_text())) if used_path.exists() else set()
        if name not in used:
            used.add(name)
            used_path.write_text(json.dumps(sorted(used)))

    def used(self) -> list[str]:
        used_path = self.cache_dir / "used.json"
        return sorted(json.loads(used_path.read_text())) if used_path.exists() else []

    def update(self, names: list[str] | None = None) -> dict[str, str]:
        """Revisa la vitrina ahora y descarga lo nuevo de los datasets indicados
        (por defecto, los que ya se usaron alguna vez)."""
        manifest = self.manifest(refresh=True)
        targets = names or [n for n in self.used() if n in manifest["datasets"]]
        return {name: (self.ensure(name), self.entry(name)["snapshot"])[1] for name in targets}

    def status(self) -> dict[str, Any]:
        manifest = self.manifest()
        return {
            "base_url": self.settings.base_url,
            "cache_dir": str(self.cache_dir),
            "snapshot": manifest["snapshot"],
            "pinned": self.snapshot is not None,
            "offline": self.settings.offline,
            "datasets": [
                {
                    "dataset": name,
                    "snapshot": e["snapshot"],
                    "record_count": e["record_count"],
                    "retrieved_at": e["retrieved_at"],
                    "cached": self.object_path(e).exists(),
                }
                for name, e in sorted(manifest["datasets"].items())
            ],
        }

    def clear_cache(self) -> None:
        self._manifest = None
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
