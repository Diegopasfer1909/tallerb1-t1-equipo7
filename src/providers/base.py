"""Contrato común de los proveedores y cliente HTTP compartido por Alpha Vantage y FRED."""

import hashlib
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from ..models.price_history import PriceHistory


class ProviderError(RuntimeError):
    """Fallo de consulta, acceso denegado o respuesta inesperada del proveedor."""


class DataCoverageError(ProviderError):
    """Los datos disponibles no cubren el intervalo solicitado."""


class PriceProvider(Protocol):
    """Lo que el resto del programa necesita de cualquier fuente de precios.

    Las opciones propias de cada proveedor se indican al crear el adaptador, de modo
    que añadir una fuente nueva no obliga a cambiar la carga ni el análisis.
    """

    def get_prices(
        self, symbol: str, start: str, end: str, *, adjusted: bool = False
    ) -> PriceHistory: ...


# Claves comunes de PriceHistory.info; cada adaptador traduce su ficha a estas claves.
INFO_FIELDS = ("currency", "name", "asset_type", "sector", "country")
NUMERIC_INFO_FIELDS = ("beta", "market_cap", "pe_ratio")


def normalize_info(
    raw: dict, fields: dict[str, tuple[str, ...]], asset_types: dict[str, str]
) -> dict:
    """Traduce la ficha del proveedor a las claves comunes y conserva el original en raw.

    fields indica, para cada clave común, los nombres que usa el proveedor por orden de
    preferencia. Los valores ausentes quedan como None (texto) o NaN (números).
    """
    info: dict = {"raw": raw}
    for name in (*INFO_FIELDS, *NUMERIC_INFO_FIELDS):
        candidates = [raw.get(key) for key in fields.get(name, ())]
        value = next((v for v in candidates if v not in (None, "", "None", "-")), None)
        if name in NUMERIC_INFO_FIELDS:
            info[name] = _number(value)
        elif name == "asset_type":
            info[name] = asset_types.get(str(value), "unknown")
        else:
            info[name] = str(value) if value is not None else None
    return info


def _number(value) -> float:
    """Acepta cifras en texto; una beta nula o negativa es válida."""
    if isinstance(value, bool):
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def date_range(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Exige fechas AAAA-MM-DD; todos los proveedores incluyen el inicio y excluyen el final."""
    try:
        first = pd.Timestamp(datetime.strptime(start, "%Y-%m-%d"))
        last = pd.Timestamp(datetime.strptime(end, "%Y-%m-%d"))
    except (ValueError, TypeError):
        raise ValueError(
            "Utiliza fechas válidas con el formato AAAA-MM-DD, por ejemplo 2026-10-01."
        ) from None
    if first >= last:
        raise ValueError("La fecha de inicio debe ser anterior a la fecha final.")
    return first, last


class ApiClient:
    """Descarga JSON y permite reutilizar respuestas guardadas en disco."""

    def __init__(
        self,
        api_key: str | None,
        env_name: str,
        *,
        cache_dir: Path | None = None,
        cache_ttl: float = 86400,
        session: requests.Session | None = None,
        min_interval: float = 0,
    ):
        if api_key is None:
            api_key = os.getenv(env_name, "")
        self.api_key = api_key.strip()
        if not self.api_key:
            raise ValueError(
                f"Configura {env_name} en el entorno o en el archivo .env del proyecto."
            )
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.cache_ttl = cache_ttl
        if session is None:
            session = requests.Session()
        self.session = session
        self.min_interval = min_interval
        self._last_request: float | None = None

    def get_json(self, url: str, params: dict) -> dict:
        cache = None
        if self.cache_dir is not None:
            # La misma consulta produce el mismo nombre de archivo sin exponer la clave.
            request = json.dumps([url, params], sort_keys=True)
            name = hashlib.sha256(request.encode()).hexdigest()
            cache = self.cache_dir / f"{name}.json"
        cached = self._read_cache(cache)
        if cached is not None:
            return cached

        if self._last_request is not None:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()

        data = self._download(url, params)
        self._write_cache(cache, data)
        return data

    def _read_cache(self, cache: Path | None) -> dict | None:
        """Devuelve una respuesta vigente o None si se necesita descargarla."""
        if cache is None or self.cache_ttl <= 0:
            return None
        try:
            age = time.time() - cache.stat().st_mtime
            if age < self.cache_ttl:
                cached = json.loads(cache.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached:
                    return cached
        except (OSError, ValueError):
            pass
        return None

    def _download(self, url: str, params: dict) -> dict:
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
        except requests.HTTPError as error:
            status = "unknown"
            if error.response is not None:
                status = error.response.status_code
            raise ProviderError(f"El proveedor ha devuelto el estado HTTP {status}.") from None
        except requests.RequestException:
            # Las excepciones de requests pueden contener claves en la URL; no las muestres.
            raise ProviderError(
                "No se ha podido conectar con el proveedor. Comprueba la conexión o inténtalo más tarde."
            ) from None
        try:
            payload = response.json()
        except ValueError:
            raise ProviderError("El proveedor ha devuelto un JSON no válido.") from None
        if not isinstance(payload, dict) or not payload:
            raise ProviderError("El proveedor ha devuelto una respuesta vacía o inesperada.")
        # Un estado HTTP 200 también puede contener errores de cuota o permisos.
        for field in ("Error Message", "Note", "Information", "error_message"):
            if field in payload:
                message = str(payload[field]).replace(self.api_key, "[redacted]")
                raise ProviderError(
                    f"El proveedor ha rechazado la consulta. Mensaje original: {message}"
                )
        return payload

    def _write_cache(self, cache: Path | None, payload: dict) -> None:
        """Guarda la respuesta si se ha activado la caché, sin impedir la consulta si falla."""
        if cache is None:
            return
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            # Un fallo al guardar la caché no debe impedir una descarga correcta.
            pass
