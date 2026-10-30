"""Contrato común de los proveedores y cliente HTTP compartido por Alpha Vantage y ALFRED."""

import contextlib
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from ..constants import CLOSE
from ..errors import ConfigurationError
from ..models.asset_profile import AssetProfile
from ..models.price_history import PriceHistory

# Valores con los que los proveedores indican que falta un dato de la ficha.
MISSING_VALUES = (None, "", "None", "-")
# Solo se eliminan archivos con el nombre que genera la caché: el resumen de la consulta.
CACHE_FILE = re.compile(r"\.?[0-9a-f]{64}\.json(\.\d+\.tmp)?")


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


def build_profile(
    raw: dict,
    fields: dict[str, tuple[str, ...]],
    asset_types: dict[str, str],
    issue: str | None = None,
) -> AssetProfile:
    """Traduce la ficha del proveedor a la ficha común y conserva el original en raw.

    fields indica, para cada campo común, los nombres que usa el proveedor por orden de
    preferencia. Los textos ausentes quedan como None y las cifras, como NaN.
    """

    def first(name: str):
        values = (raw.get(key) for key in fields.get(name, ()))
        return next((value for value in values if value not in MISSING_VALUES), None)

    def text(name: str) -> str | None:
        value = first(name)
        return str(value) if value is not None else None

    return AssetProfile(
        currency=text("currency"),
        name=text("name"),
        asset_type=asset_types.get(str(first("asset_type")), "unknown"),
        sector=text("sector"),
        country=text("country"),
        beta=_number(first("beta")),
        market_cap=_number(first("market_cap")),
        pe_ratio=_number(first("pe_ratio")),
        raw=dict(raw),
        issue=issue,
    )


def _number(value) -> float:
    """Acepta cifras en texto; una beta nula o negativa es válida."""
    if isinstance(value, bool):
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def has_api_key(env_name: str) -> bool:
    """Indica si la clave está configurada en el entorno (o en .env, una vez cargado)."""
    return bool(os.getenv(env_name, "").strip())


def drop_missing_closes(prices: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Descarta las fechas sin cierre en lugar de rechazar todo el historial."""
    if CLOSE not in prices.columns:
        return prices, 0
    missing = prices[CLOSE].isna()
    return prices.loc[~missing], int(missing.sum())


class ApiClient:
    """Descarga JSON y permite reutilizar respuestas guardadas en disco.

    error_keys son los campos con los que el proveedor comunica errores dentro de una
    respuesta HTTP 200. Con cache_ttl igual a cero no se utiliza la caché.
    """

    def __init__(
        self,
        api_key: str | None,
        env_name: str,
        *,
        error_keys: tuple[str, ...] = (),
        cache_dir: Path | None = None,
        cache_ttl: float = 86400,
        session: requests.Session | None = None,
        min_interval: float = 0,
    ):
        if api_key is None:
            api_key = os.getenv(env_name, "")
        self.api_key = api_key.strip()
        if not self.api_key:
            raise ConfigurationError(
                f"Configura {env_name} en el entorno o en el archivo .env del proyecto."
            )
        self.error_keys = tuple(error_keys)
        self.cache_dir = Path(cache_dir) if cache_dir is not None and cache_ttl > 0 else None
        self.cache_ttl = cache_ttl
        self.session = session if session is not None else requests.Session()
        self.min_interval = min_interval
        self._last_request: float | None = None
        self._prune_cache()

    def get_json(self, url: str, params: dict) -> dict:
        cache = self._cache_path(url, params)
        cached = self._read_cache(cache)
        if cached is not None:
            return cached
        self._wait_for_rate_limit()
        data = self._download(url, params)
        self._write_cache(cache, data)
        return data

    def _cache_path(self, url: str, params: dict) -> Path | None:
        """La misma consulta produce el mismo nombre de archivo sin exponer la clave."""
        if self.cache_dir is None:
            return None
        request = json.dumps([url, params], sort_keys=True)
        return self.cache_dir / f"{hashlib.sha256(request.encode()).hexdigest()}.json"

    def _is_fresh(self, path: Path) -> bool:
        return time.time() - path.stat().st_mtime < self.cache_ttl

    def _read_cache(self, cache: Path | None) -> dict | None:
        """Devuelve una respuesta vigente; una caducada o vacía se elimina."""
        if cache is None:
            return None
        with contextlib.suppress(OSError, ValueError):
            if self._is_fresh(cache):
                cached = json.loads(cache.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached:
                    return cached
            cache.unlink()
        return None

    def _prune_cache(self) -> None:
        """Elimina las respuestas caducadas para que la caché no crezca sin límite."""
        if self.cache_dir is None or not self.cache_dir.is_dir():
            return
        for path in self.cache_dir.iterdir():
            if CACHE_FILE.fullmatch(path.name):
                with contextlib.suppress(OSError):
                    if not self._is_fresh(path):
                        path.unlink()

    def _wait_for_rate_limit(self) -> None:
        """Respeta el intervalo mínimo entre peticiones reales; la caché no cuenta."""
        if self._last_request is not None:
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()

    def _download(self, url: str, params: dict) -> dict:
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
        except requests.HTTPError as error:
            status, reason = "unknown", None
            if error.response is not None:
                status = error.response.status_code
                reason = self._rejection(error.response)
            detail = f" Mensaje original: {reason}" if reason else ""
            raise ProviderError(
                f"El proveedor ha devuelto el estado HTTP {status}.{detail}"
            ) from None
        except requests.RequestException:
            # Las excepciones de requests pueden contener claves en la URL; no las muestres.
            raise ProviderError(
                "No se ha podido conectar con el proveedor. Comprueba la conexión o inténtalo "
                "más tarde."
            ) from None
        try:
            payload = response.json()
        except ValueError:
            raise ProviderError("El proveedor ha devuelto un JSON no válido.") from None
        if not isinstance(payload, dict) or not payload:
            raise ProviderError("El proveedor ha devuelto una respuesta vacía o inesperada.")
        # Un estado HTTP 200 también puede contener errores de cuota o permisos.
        reason = self._rejection(response)
        if reason:
            raise ProviderError(
                f"El proveedor ha rechazado la consulta. Mensaje original: {reason}"
            )
        return payload

    def _rejection(self, response) -> str | None:
        """Motivo que da el proveedor (clave no válida, cuota…), sin mostrar la clave."""
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        for key in self.error_keys:
            if key in payload:
                return str(payload[key]).replace(self.api_key, "[redacted]")
        return None

    def _write_cache(self, cache: Path | None, payload: dict) -> None:
        """Guarda la respuesta de forma atómica; un fallo no impide la consulta."""
        if cache is None:
            return
        temporary = cache.with_name(f".{cache.name}.{os.getpid()}.tmp")
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary, cache)
        except OSError:
            with contextlib.suppress(OSError):
                temporary.unlink(missing_ok=True)
