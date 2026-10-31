"""Cuota persistente de Alpha Vantage, compartida por clave y entre procesos."""

import hashlib
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .base import ProviderError

DAILY_LIMIT = 25
WINDOW_SECONDS = 24 * 60 * 60
# Pausa ante un aviso de ritmo (peticiones por segundo o por minuto), no de cuota diaria.
THROTTLE_SECONDS = 60
USAGE_DB_ENV = "ALPHA_VANTAGE_USAGE_DB"
# Los mensajes de cuota pueden llegar en Note o Information con HTTP 200.
QUOTA_PHRASES = (
    "rate limit",
    "requests per day",
    "quota reached",
    "quota exhausted",
    "quota exceeded",
    "quota has been reached",
    "quota has been exhausted",
    "quota has been exceeded",
)
# Avisos de ritmo; se comprueban antes que la cuota porque el antiguo aviso de "call
# frequency" menciona a la vez el límite por minuto y el diario.
THROTTLE_PHRASES = ("per second", "per minute", "sparingly", "call frequency", "too many requests")


def rejection_cooldown(status: int, reason: str | None) -> float | None:
    """Segundos que se bloquean los envíos tras un rechazo; None si no es un límite de uso.

    Solo el límite diario bloquea 24 horas. Un aviso de ritmo, o un HTTP 429 sin más
    detalle, pausa THROTTLE_SECONDS para no dejar la clave inutilizable todo el día.
    """
    text = (reason or "").lower()
    if any(phrase in text for phrase in THROTTLE_PHRASES):
        return THROTTLE_SECONDS
    if any(phrase in text for phrase in QUOTA_PHRASES):
        return WINDOW_SECONDS
    return THROTTLE_SECONDS if status == 429 else None


class AlphaVantageQuotaError(ProviderError):
    """Cuota local o remota agotada; retry_at indica cuándo se permite volver a intentar."""

    def __init__(self, retry_at: float, *, remote: bool = False, request_sent: bool = False):
        self.retry_at = retry_at
        self.remote = remote
        retry = datetime.fromtimestamp(retry_at, timezone.utc).isoformat(timespec="seconds")
        if remote:
            reason = (
                "Alpha Vantage ha rechazado una consulta por su límite de uso. "
                "La clave puede haber consumido cuota en CI u otros equipos. "
                f"Por precaución, los nuevos envíos se bloquean localmente hasta {retry} (UTC). "
            )
        else:
            reason = (
                f"Alpha Vantage: se ha alcanzado el límite de {DAILY_LIMIT} peticiones en 24 horas. "
                f"Próxima petición disponible a partir de {retry} (UTC). "
            )
        outcome = (
            "El proveedor ha rechazado la consulta; no se reintentará automáticamente. "
            if request_sent
            else "No se ha enviado la consulta. "
        )
        super().__init__(reason + outcome + "Las respuestas en caché siguen disponibles.")


class AlphaVantageQuota:
    """Reserva antes del envío, incluso si este falla; nunca devuelve cuota consumida.

    Una ventana móvil evita depender de la zona horaria de reinicio del proveedor.
    SQLite serializa las reservas de todos los procesos que usan el mismo archivo.
    El registro es independiente de la caché y solo almacena el hash de la clave.
    """

    def __init__(self, api_key: str, path: str | Path | None = None):
        default = Path.home() / ".local" / "state" / "miax" / "alpha-vantage.sqlite3"
        self.path = Path(path or os.getenv(USAGE_DB_ENV) or default).expanduser().resolve()
        self.key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        self._blocked_until = 0.0

    @staticmethod
    def _create_cooldowns(connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS cooldowns "
            "(key_hash TEXT PRIMARY KEY, blocked_until REAL NOT NULL)"
        )

    def handle_rejection(self, status: int, reason: str | None) -> None:
        """La respuesta remota prevalece aunque queden reservas locales disponibles.

        Sin una hora de reinicio fiable, el límite diario se espera 24 horas desde el
        rechazo; un aviso de ritmo, solo THROTTLE_SECONDS. Un bloqueo más largo ya guardado
        no se acorta. No se guardan ni la clave ni el mensaje original. Un error de permisos
        o de un endpoint premium sigue siendo ProviderError y no bloquea otros endpoints.
        """
        cooldown = rejection_cooldown(status, reason)
        if cooldown is None:
            return
        self._blocked_until = max(self._blocked_until, time.time() + cooldown)
        try:
            with closing(sqlite3.connect(self.path, timeout=30)) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                self._create_cooldowns(connection)
                connection.execute(
                    "INSERT INTO cooldowns (key_hash, blocked_until) VALUES (?, ?) "
                    "ON CONFLICT(key_hash) DO UPDATE SET "
                    "blocked_until = MAX(cooldowns.blocked_until, excluded.blocked_until)",
                    (self.key_hash, self._blocked_until),
                )
                (self._blocked_until,) = connection.execute(
                    "SELECT blocked_until FROM cooldowns WHERE key_hash = ?", (self.key_hash,)
                ).fetchone()
        except (OSError, sqlite3.Error):
            retry = datetime.fromtimestamp(self._blocked_until, timezone.utc)
            raise ProviderError(
                "Alpha Vantage ha rechazado una consulta por su límite de uso, pero no se ha "
                "podido guardar el bloqueo. Este cliente no enviará más consultas hasta "
                f"{retry.isoformat(timespec='seconds')} (UTC). Comprueba {USAGE_DB_ENV} y "
                "sus permisos."
            ) from None
        raise AlphaVantageQuotaError(self._blocked_until, remote=True, request_sent=True)

    def reserve(self) -> None:
        """Bloquea la consulta si no puede comprobar y guardar la cuota con seguridad."""
        if self._blocked_until > time.time():
            raise AlphaVantageQuotaError(self._blocked_until, remote=True)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=30)) as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS requests "
                    "(key_hash TEXT NOT NULL, requested_at REAL NOT NULL)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS requests_key_time "
                    "ON requests (key_hash, requested_at)"
                )
                now = time.time()
                self._create_cooldowns(connection)
                cooldown = connection.execute(
                    "SELECT blocked_until FROM cooldowns WHERE key_hash = ?", (self.key_hash,)
                ).fetchone()
                if cooldown and cooldown[0] > now:
                    self._blocked_until = cooldown[0]
                    raise AlphaVantageQuotaError(self._blocked_until, remote=True)
                connection.execute(
                    "DELETE FROM requests WHERE requested_at <= ?", (now - WINDOW_SECONDS,)
                )
                count, oldest = connection.execute(
                    "SELECT COUNT(*), MIN(requested_at) FROM requests WHERE key_hash = ?",
                    (self.key_hash,),
                ).fetchone()
                if count >= DAILY_LIMIT:
                    raise AlphaVantageQuotaError(oldest + WINDOW_SECONDS)
                connection.execute(
                    "INSERT INTO requests (key_hash, requested_at) VALUES (?, ?)",
                    (self.key_hash, now),
                )
        except (OSError, sqlite3.Error):
            raise ProviderError(
                "No se ha podido comprobar o guardar la cuota de Alpha Vantage. "
                f"Comprueba el archivo configurado con {USAGE_DB_ENV} y sus permisos. "
                "No se ha enviado la consulta."
            ) from None
