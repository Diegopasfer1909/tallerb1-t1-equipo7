"""Descarga en lote los historiales de varios activos, con varios hilos si el proveedor lo admite.

Las esperas de red de activos distintos se solapan con ThreadPoolExecutor. El resultado no
depende del orden en que terminen las descargas: siempre sigue el orden de los símbolos.
"""

import contextlib
import re
from collections.abc import Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from itertools import islice

from .errors import PortfolioError
from .models import PriceHistory
from .providers import PriceProvider, ProviderError
from .validation import date_range, validate_symbols

# Límite de descargas simultáneas por lote en esta versión.
MAX_DOWNLOAD_WORKERS = 4
WORKERS_ERROR = (
    f"El número de descargas simultáneas debe ser un entero entre 1 y {MAX_DOWNLOAD_WORKERS}."
)


def validate_download_workers(value) -> None:
    """Entero entre 1 y MAX_DOWNLOAD_WORKERS; los booleanos no cuentan como números."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise PortfolioError(WORKERS_ERROR)
    if not 1 <= value <= MAX_DOWNLOAD_WORKERS:
        raise PortfolioError(WORKERS_ERROR)


def download_capacity(provider: PriceProvider) -> int:
    """Descargas simultáneas que admite el proveedor; 1 si no lo declara.

    Un proveedor lo declara con un atributo entero max_download_workers. Cualquier otro
    valor (un booleano, el atributo dinámico de un Mock…) equivale a no declararlo.
    """
    capacity = getattr(provider, "max_download_workers", 1)
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
        return 1
    return capacity


def effective_download_workers(provider: PriceProvider, requested: int, symbols: int) -> int:
    """Lo que pide el usuario, sin superar el proveedor, el límite de la versión ni los activos."""
    return max(1, min(requested, download_capacity(provider), MAX_DOWNLOAD_WORKERS, symbols))


def load_price_histories(
    symbols: Sequence[str],
    provider: PriceProvider,
    start: str,
    end: str,
    *,
    max_workers: int = 1,
) -> list[PriceHistory]:
    """Una llamada a get_prices() por símbolo; los historiales vuelven en el orden recibido.

    Valida los símbolos, las fechas y max_workers antes de consultar el proveedor. Con un
    solo trabajador efectivo se descarga en secuencia, sin crear hilos. Si falla un
    historial, se deja de enviar descargas, se cancelan las pendientes y se propaga el
    error con el símbolo: nunca se devuelve un lote parcial.
    """
    symbols = list(symbols)
    validate_symbols(symbols)
    date_range(start, end)
    validate_download_workers(max_workers)
    symbols = [symbol.strip() for symbol in symbols]
    workers = effective_download_workers(provider, max_workers, len(symbols))
    if workers == 1:
        return [_download(provider, symbol, start, end) for symbol in symbols]
    return _download_concurrently(provider, symbols, start, end, workers)


def _download(provider: PriceProvider, symbol: str, start: str, end: str) -> PriceHistory:
    try:
        return provider.get_prices(symbol, start, end)
    except (PortfolioError, ProviderError) as error:
        _name_symbol(error, symbol)
        raise


def _name_symbol(error: Exception, symbol: str) -> None:
    """Añade el símbolo al mensaje visible conservando el tipo y los atributos del error.

    La consola muestra str(error), así que add_note() no bastaría. Solo se modifica un
    mensaje simple que aún no nombre el activo.
    """
    if len(error.args) != 1 or not isinstance(error.args[0], str):
        return
    message = error.args[0]
    # Un punto final no forma parte del símbolo; el de BRK.B, sí.
    if re.search(rf"(?<![\w.^=-]){re.escape(symbol)}(?![\w=-]|\.\w)", message):
        return
    error.args = (f"{symbol}: {message}",)


def _download_concurrently(
    provider: PriceProvider, symbols: list[str], start: str, end: str, workers: int
) -> list[PriceHistory]:
    """Mantiene como mucho workers descargas en vuelo y repone una al terminar otra."""
    results: list[PriceHistory | None] = [None] * len(symbols)
    queue = iter(enumerate(symbols))
    running: dict[Future, int] = {}
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="price-download")
    try:
        for index, symbol in islice(queue, workers):
            running[executor.submit(_download, provider, symbol, start, end)] = index
        while running:
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            # Si fallan varias a la vez, se informa del primer activo de la lista.
            for future in sorted(done, key=running.__getitem__):
                results[running.pop(future)] = future.result()
            for index, symbol in islice(queue, len(done)):
                running[executor.submit(_download, provider, symbol, start, end)] = index
    except BaseException:
        # También ante Ctrl+C: no se envía nada más y se cancela lo que no ha empezado. Las
        # descargas en curso terminan por su cuenta, como mucho al agotar su timeout HTTP.
        for future in running:
            future.cancel()
        with contextlib.suppress(Exception):
            executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    return results
