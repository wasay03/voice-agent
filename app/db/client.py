"""DatabaseClient: the only place that owns PostgreSQL connections.

Responsibilities: pool lifecycle, transactions, JSON codecs, timeouts and translating asyncpg
errors into `app.core.errors`. It knows nothing about patients or calls; repositories call it
with `SELECT * FROM fn_...` (reads) or `CALL sp_...` (writes).
"""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from app.core.errors import (
    AppError,
    ConflictError,
    DatabaseTimeoutError,
    DatabaseUnavailableError,
    DataIntegrityError,
)
from app.core.logging import get_logger

log = get_logger(__name__)

# Errors that mean "the connection is gone"; a read outside a transaction may retry once.
_CONNECTION_LOST = (
    asyncpg.ConnectionDoesNotExistError,
    asyncpg.exceptions.AdminShutdownError,  # Neon suspending compute terminates connections
)
_UNAVAILABLE = (
    asyncpg.PostgresConnectionError,
    asyncpg.InterfaceError,
    asyncpg.exceptions.CannotConnectNowError,
    asyncpg.exceptions.AdminShutdownError,
    OSError,
)


def translate_db_error(exc: BaseException) -> AppError:
    """Map a driver exception onto the application error hierarchy."""
    if isinstance(exc, AppError):
        return exc
    if isinstance(exc, asyncpg.UniqueViolationError):
        return ConflictError(exc.message)
    if isinstance(exc, asyncpg.IntegrityConstraintViolationError | asyncpg.DataError):
        return DataIntegrityError(
            exc.message,
            constraint=getattr(exc, "constraint_name", None),
            column=getattr(exc, "column_name", None),
        )
    if isinstance(exc, asyncpg.QueryCanceledError | TimeoutError):
        return DatabaseTimeoutError()
    if isinstance(exc, _UNAVAILABLE):
        return DatabaseUnavailableError()
    return AppError("Unexpected database error.")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)


async def _init_connection(conn: asyncpg.Connection) -> None:
    for type_name in ("json", "jsonb"):
        await conn.set_type_codec(type_name, encoder=_json_dumps, decoder=json.loads, schema="pg_catalog")


class DatabaseClient:
    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 5,
        statement_timeout_ms: int = 3000,
        max_inactive_seconds: float = 60.0,
        application_name: str = "voice-intake",
    ) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._statement_timeout_ms = statement_timeout_ms
        self._max_inactive_seconds = max_inactive_seconds
        self._application_name = application_name
        self._pool: asyncpg.Pool | None = None

    # -- lifecycle -------------------------------------------------------------------------

    async def connect(self) -> None:
        if self._pool is not None:
            return
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                # Drop idle connections before Neon's scale-to-zero kills them under us.
                max_inactive_connection_lifetime=self._max_inactive_seconds,
                command_timeout=self._statement_timeout_ms / 1000 + 1,
                server_settings={
                    "statement_timeout": str(self._statement_timeout_ms),
                    "application_name": self._application_name,
                    "timezone": "UTC",
                },
                init=_init_connection,
            )
        except Exception as exc:
            raise translate_db_error(exc) from exc
        log.info("db.connected", pool_min=self._min_size, pool_max=self._max_size)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            log.info("db.closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DatabaseClient.connect() has not been called")
        return self._pool

    async def ping(self, wait_seconds: float = 2.0) -> bool:
        try:
            async with self.pool.acquire(timeout=wait_seconds) as conn:
                return await conn.fetchval("SELECT 1", timeout=wait_seconds) == 1
        except Exception as exc:
            log.warning("db.ping_failed", error=type(exc).__name__)
            return False

    # -- transactions ----------------------------------------------------------------------

    @asynccontextmanager
    async def transaction(self, *, readonly: bool = False) -> AsyncIterator[asyncpg.Connection]:
        """Yield one connection inside a transaction; commit on success, roll back on error."""
        try:
            async with self.pool.acquire() as conn, conn.transaction(readonly=readonly):
                yield conn
        except AppError:
            raise
        except Exception as exc:
            if isinstance(exc, asyncpg.PostgresError | _UNAVAILABLE | TimeoutError):
                raise translate_db_error(exc) from exc
            raise

    # -- query helpers ---------------------------------------------------------------------

    async def fetch_one(
        self, sql: str, *args: Any, conn: asyncpg.Connection | None = None, idempotent: bool = False
    ) -> asyncpg.Record | None:
        return await self._run("fetchrow", sql, args, conn, idempotent)

    async def fetch_all(
        self, sql: str, *args: Any, conn: asyncpg.Connection | None = None, idempotent: bool = False
    ) -> list[asyncpg.Record]:
        return await self._run("fetch", sql, args, conn, idempotent)

    async def execute(self, sql: str, *args: Any, conn: asyncpg.Connection | None = None) -> None:
        await self._run("execute", sql, args, conn, idempotent=False)

    async def _run(
        self,
        method: str,
        sql: str,
        args: Sequence[Any],
        conn: asyncpg.Connection | None,
        idempotent: bool,
    ) -> Any:
        # Retrying is only safe for reads outside a caller-owned transaction.
        attempts = 2 if (idempotent and conn is None) else 1
        for attempt in range(1, attempts + 1):
            try:
                if conn is not None:
                    return await getattr(conn, method)(sql, *args)
                async with self.pool.acquire() as pooled:
                    return await getattr(pooled, method)(sql, *args)
            except _CONNECTION_LOST as exc:
                if attempt < attempts:
                    log.warning("db.retry_after_connection_lost", error=type(exc).__name__)
                    continue
                raise translate_db_error(exc) from exc
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise translate_db_error(exc) from exc
        raise AssertionError("unreachable")
