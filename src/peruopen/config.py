"""Configuración: de dónde se leen los datos y dónde se guardan.

Variables de entorno:
- PERUOPEN_BASE_URL: URL pública de la vitrina (o una carpeta local).
- PERUOPEN_CACHE_DIR: carpeta de caché (por defecto la del sistema).
- PERUOPEN_OFFLINE=1: no usar la red, solo la caché.
- PERUOPEN_CHECK_HOURS: cada cuántas horas se revisa si hay datos nuevos (24).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from platformdirs import user_cache_dir

from .exceptions import ConfigError

# URL pública del bucket de Cloudflare R2. Se completa cuando exista el
# dominio público; mientras tanto se usa PERUOPEN_BASE_URL.
DEFAULT_BASE_URL: str | None = None

_TRUE = {"1", "true", "yes", "si", "sí"}


@dataclass(frozen=True)
class Settings:
    base_url: str
    cache_dir: Path
    offline: bool
    check_interval: timedelta


def load_settings(
    *,
    base_url: str | None = None,
    cache_dir: str | Path | None = None,
    offline: bool | None = None,
) -> Settings:
    url = base_url or os.environ.get("PERUOPEN_BASE_URL") or DEFAULT_BASE_URL
    if not url:
        raise ConfigError(
            "No hay una vitrina configurada. Define la variable de entorno "
            "PERUOPEN_BASE_URL (URL pública de los datos o una carpeta local), "
            "o pasa base_url= a peruopen.connect()."
        )
    cache = Path(cache_dir or os.environ.get("PERUOPEN_CACHE_DIR") or user_cache_dir("peruopen"))
    if offline is None:
        offline = os.environ.get("PERUOPEN_OFFLINE", "").strip().lower() in _TRUE
    hours = float(os.environ.get("PERUOPEN_CHECK_HOURS", "24"))
    return Settings(
        base_url=url,
        cache_dir=cache,
        offline=offline,
        check_interval=timedelta(hours=hours),
    )
