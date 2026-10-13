"""Base class for repositories: every method is one routine call, nothing else.

Reads go through `_fn_*` (`SELECT ... FROM fn_x(...)`), writes through `_sp` (`CALL sp_x(...)`).
A repository bound to a connection runs inside the caller's unit of work; an unbound one takes a
connection from the pool per call, and its reads may retry once after a dropped connection.
"""

import re
from collections.abc import Sequence
from typing import Any

import asyncpg

from app.db.client import DatabaseClient

_ROUTINE_NAME = re.compile(r"^(fn|sp)_[a-z0-9_]+$")


def _placeholders(count: int, start: int = 1) -> str:
    return ", ".join(f"${i}" for i in range(start, start + count))


def _checked(name: str, prefix: str) -> str:
    if not _ROUTINE_NAME.match(name) or not name.startswith(prefix):
        raise ValueError(f"invalid routine name {name!r}")
    return name


class BaseRepository:
    def __init__(self, db: DatabaseClient, conn: asyncpg.Connection | None = None) -> None:
        self._db = db
        self._conn = conn

    async def _fn_value(self, name: str, *args: Any) -> Any:
        """Scalar-returning function: SELECT fn_x(...)."""
        row = await self._db.fetch_one(
            f"SELECT {_checked(name, 'fn_')}({_placeholders(len(args))}) AS value",
            *args,
            conn=self._conn,
            idempotent=True,
        )
        return row["value"] if row else None

    async def _fn_rows(self, name: str, *args: Any) -> list[asyncpg.Record]:
        """Set-returning function: SELECT * FROM fn_x(...)."""
        return await self._db.fetch_all(
            f"SELECT * FROM {_checked(name, 'fn_')}({_placeholders(len(args))})",
            *args,
            conn=self._conn,
            idempotent=True,
        )

    async def _sp(self, name: str, *args: Any, outputs: Sequence[str] = ()) -> asyncpg.Record | None:
        """CALL sp_x(args..., NULL::type...) — `outputs` lists the SQL types of the INOUT parameters.

        Returns the row of INOUT values, or None for a procedure without any.
        """
        out = ", ".join(f"NULL::{t}" for t in outputs)
        params = ", ".join(p for p in (_placeholders(len(args)), out) if p)
        sql = f"CALL {_checked(name, 'sp_')}({params})"
        if outputs:
            return await self._db.fetch_one(sql, *args, conn=self._conn)
        await self._db.execute(sql, *args, conn=self._conn)
        return None
