"""Unit of work: the only way services reach repositories.

    async with self.uow() as repos:                     # one transaction, all repos share it
        session = await repos.call_sessions.lock(call_id)
        patient = await repos.patients.create(payload)

    async with self.uow(transactional=False) as repos:  # single read: pooled, retried once
        patient = await repos.patients.get_by_id(patient_id)

Commits when the block exits normally and rolls back on any exception. Services never see a
connection or SQL; they only call repository methods.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import asyncpg

from app.db.client import DatabaseClient
from app.db.repositories.patient_repository import PatientRepository


@dataclass(frozen=True)
class Repositories:
    patients: PatientRepository


class UnitOfWork:
    def __init__(self, db: DatabaseClient) -> None:
        self._db = db

    def _bind(self, conn: asyncpg.Connection | None) -> Repositories:
        return Repositories(patients=PatientRepository(self._db, conn))

    @asynccontextmanager
    async def __call__(
        self, *, transactional: bool = True, readonly: bool = False
    ) -> AsyncIterator[Repositories]:
        if not transactional:
            yield self._bind(None)
            return
        async with self._db.transaction(readonly=readonly) as conn:
            yield self._bind(conn)
