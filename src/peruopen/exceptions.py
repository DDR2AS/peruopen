"""Errores de peruopen. Todos heredan de `PeruOpenError`."""

from __future__ import annotations


class PeruOpenError(Exception):
    """Base de todos los errores de peruopen."""


class ConfigError(PeruOpenError):
    """Falta configuración (p. ej. la URL de la vitrina)."""


class DataUnavailableError(PeruOpenError):
    """No se pudo obtener el dato: sin red y sin caché, o la vitrina no responde."""


class DatasetNotFoundError(PeruOpenError, KeyError):
    """El dataset pedido no existe en el manifest."""

    def __str__(self) -> str:  # KeyError pone comillas al mensaje
        return str(self.args[0]) if self.args else ""


class IntegrityError(PeruOpenError):
    """El archivo descargado no coincide con el sha256 del manifest."""


class ReadOnlyQueryError(PeruOpenError, ValueError):
    """La consulta no está permitida en modo solo lectura (MCP)."""
