"""Precios históricos y ficha del activo en Yahoo Finance."""

import json
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

from ..errors import DataCoverageError, ProviderError
from ..models.asset_profile import AssetProfile
from ..models.price_history import PriceHistory
from ..validation import date_range
from .base import (
    build_profile,
    cache_lock,
    cache_path,
    drop_missing_closes,
    prune_cache,
    read_cache,
    write_cache,
)

FIELDS = {
    "currency": ("currency",),
    "name": ("longName", "shortName"),
    "asset_type": ("quoteType",),
    "sector": ("sector",),
    "country": ("country",),
    "beta": ("beta", "beta3Year"),
    "market_cap": ("marketCap",),
    "pe_ratio": ("trailingPE",),
}
ASSET_TYPES = {"EQUITY": "stock", "INDEX": "index", "ETF": "etf", "MUTUALFUND": "fund"}
# Solo estos publican su composición por tipo de activo.
FUND_TYPES = ("ETF", "MUTUALFUND")
# Segundos de espera de cada petición de precios; la ficha usa el límite propio de yfinance
# (30 s), así que ninguna descarga puede quedarse esperando indefinidamente.
HTTP_TIMEOUT = 30
PROFILE_ISSUE = (
    "No se ha podido consultar la ficha del activo en Yahoo Finance. Es posible que se haya "
    "alcanzado el límite de consultas o que el símbolo no tenga ficha. Faltan la divisa y los "
    "datos de la empresa; indica la divisa expresamente."
)


class YahooFinanceAPI:
    """Adaptador de Yahoo Finance; sus opciones propias se fijan al crearlo.

    Con cache_dir, cada símbolo guarda su ficha y un único historial que cubre todas las
    fechas ya consultadas, de modo que cambiar otros activos, los parámetros de la
    simulación o acortar el intervalo no repite descargas. Con cache_ttl igual a cero no se
    utiliza la caché. include_info=False omite la ficha cuando solo se necesitan precios,
    como en los tipos de cambio.

    Admite hasta max_download_workers descargas simultáneas de activos distintos: cada
    entrada de la caché se lee, amplía y escribe con su propio bloqueo, y cada operación
    usa su propio Ticker. Los filtros de avisos no se modifican aquí (ver
    quiet_yfinance_warnings).
    """

    max_download_workers = 4

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: float = 86400,
        *,
        include_info: bool = True,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir is not None and cache_ttl > 0 else None
        self.cache_ttl = cache_ttl
        self.include_info = include_info
        prune_cache(self.cache_dir, cache_ttl)

    def get_info(self, symbol: str) -> dict:
        """Consulta la ficha del activo; yfinance la obtiene con una petición adicional."""
        cache = cache_path(self.cache_dir, ["yahoo", "profile", symbol])
        # Dos solicitudes simultáneas de la misma ficha comparten una sola descarga.
        with cache_lock(cache):
            cached = read_cache(cache, self.cache_ttl)
            if cached is not None:
                return cached
            info = _download_info(symbol)
            write_cache(cache, info)
            return info

    def get_prices(
        self, symbol: str, start: str, end: str, *, adjusted: bool = False
    ) -> PriceHistory:
        """Descarga los datos de Yahoo, normaliza las fechas y crea el historial."""
        first, last = date_range(start, end)
        history = self._history(symbol, first, last, adjusted)
        history = history.loc[(history.index >= first) & (history.index < last)]
        prices, dropped = drop_missing_closes(history)
        if prices.empty:
            raise DataCoverageError(
                f"Yahoo no ha devuelto precios de {symbol} dentro de las fechas solicitadas."
            )
        return PriceHistory(
            symbol,
            "yahoo",
            prices,
            profile=self._profile(symbol),
            # Yahoo ajusta Close por desdoblamientos incluso con auto_adjust=False.
            price_basis="adjusted" if adjusted else "split_adjusted",
            dropped_rows=dropped,
        )

    def _profile(self, symbol: str) -> AssetProfile:
        """La ficha es complementaria: si falla, se conservan los precios ya descargados."""
        if not self.include_info:
            return build_profile({}, FIELDS, ASSET_TYPES)
        try:
            return build_profile(self.get_info(symbol), FIELDS, ASSET_TYPES)
        except ProviderError:
            return build_profile({}, FIELDS, ASSET_TYPES, issue=PROFILE_ISSUE)

    def _history(
        self, symbol: str, first: pd.Timestamp, last: pd.Timestamp, adjusted: bool
    ) -> pd.DataFrame:
        """Reutiliza el historial guardado si cubre las fechas o lo amplía en una descarga.

        El bloqueo de la entrada cubre leer, decidir la ampliación, descargar y escribir: si
        otro hilo acaba de ampliarla, se vuelve a leer ya ampliada.
        """
        cache = cache_path(self.cache_dir, ["yahoo", "prices", symbol, adjusted])
        with cache_lock(cache):
            return self._cached_or_download(cache, symbol, first, last, adjusted)

    def _cached_or_download(
        self,
        cache: Path | None,
        symbol: str,
        first: pd.Timestamp,
        last: pd.Timestamp,
        adjusted: bool,
    ) -> pd.DataFrame:
        cached = read_cache(cache, self.cache_ttl)
        if cached is not None:
            try:
                start, end = pd.Timestamp(cached["start"]), pd.Timestamp(cached["end"])
                if start <= first and last <= end:
                    return _frame(cached["prices"])
                # Una sola descarga cubre lo guardado y lo nuevo para no alternar intervalos.
                first, last = min(first, start), max(last, end)
            except (KeyError, TypeError, ValueError):
                pass

        try:
            history = yf.Ticker(symbol).history(
                start=first.date().isoformat(),
                end=last.date().isoformat(),
                auto_adjust=adjusted,
                timeout=HTTP_TIMEOUT,
            )
        except Exception:
            # yfinance no documenta sus excepciones; se traducen al error común.
            raise ProviderError(f"Yahoo no ha podido descargar los precios de {symbol}.") from None
        if history.empty:
            raise ProviderError(f"Yahoo no ha devuelto precios para {symbol}.")
        if not isinstance(history.index, pd.DatetimeIndex):
            raise ProviderError("Yahoo ha devuelto un índice de fechas no válido.")
        # Las fechas diarias corresponden al calendario de la bolsa, no a instantes UTC.
        history.index = history.index.tz_localize(None)

        # La sesión de hoy puede no haber cerrado: solo se dan por completas las anteriores.
        complete = min(last, pd.Timestamp.today().normalize())
        if first < complete:
            payload = {
                "start": first.date().isoformat(),
                "end": complete.date().isoformat(),
                "prices": {
                    **json.loads(history.to_json(orient="split", date_format="iso")),
                    "dtypes": {column: str(dtype) for column, dtype in history.dtypes.items()},
                },
            }
            write_cache(cache, payload)
        return history


def quiet_yfinance_warnings() -> None:
    """Oculta los avisos de obsolescencia que yfinance provoca en pandas 3 (Pandas4Warning).

    Según la versión de yfinance, son internos, no afectan a los datos y llenan la consola
    en cada descarga: yfinance activa sus propios DeprecationWarning al importarse. Solo se
    ocultan los avisos originados en el código de yfinance; los demás se muestran.

    Los filtros de avisos son globales del proceso: la consola llama a esta función una vez,
    antes de empezar las descargas, en lugar de cambiarlos en cada petición desde varios
    hilos. Quien use el paquete como biblioteca decide si la llama; si no, ve esos avisos.
    """
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"yfinance(\.|$)")
    warnings.filterwarnings("ignore", category=FutureWarning, module=r"yfinance(\.|$)")


def _download_info(symbol: str) -> dict:
    """Ficha de yfinance con un Ticker propio; la composición solo se pide para fondos."""
    try:
        ticker = yf.Ticker(symbol)
        info = dict(ticker.get_info())
    except Exception:
        # yfinance no documenta sus excepciones; se traducen al error común.
        raise ProviderError("Yahoo Finance no ha devuelto la ficha del activo.") from None
    # Para símbolos sin ficha, yfinance puede devolver un diccionario casi vacío.
    if not info.get("quoteType"):
        raise ProviderError("Yahoo Finance no ha devuelto la ficha del activo.")
    if info["quoteType"] in FUND_TYPES:
        info["assetClasses"] = _asset_classes(ticker)
    return info


def _asset_classes(ticker) -> dict | None:
    """La composición es complementaria: sin ella, el activo queda sin clasificar."""
    try:
        classes = ticker.funds_data.asset_classes
        return {name: float(value) for name, value in classes.items()}
    except Exception:
        # yfinance no documenta sus excepciones.
        return None


def _frame(data: dict) -> pd.DataFrame:
    """Reconstruye el historial guardado con sus fechas y tipos originales."""
    frame = pd.DataFrame(
        data["data"], index=pd.DatetimeIndex(data["index"]), columns=data["columns"]
    )
    return frame.astype(data["dtypes"])
