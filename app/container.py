"""Composition root: builds long-lived objects once and hands them to the app."""

from dataclasses import dataclass

from app.core.config import Settings
from app.db.client import DatabaseClient
from app.db.unit_of_work import UnitOfWork
from app.services.patient_service import PatientService


@dataclass
class Container:
    settings: Settings
    db: DatabaseClient
    patients: PatientService

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        db = DatabaseClient(
            settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            statement_timeout_ms=settings.db_statement_timeout_ms,
            max_inactive_seconds=settings.db_max_inactive_conn_seconds,
        )
        uow = UnitOfWork(db)
        return cls(settings=settings, db=db, patients=PatientService(uow))

    async def start(self) -> None:
        await self.db.connect()

    async def stop(self) -> None:
        await self.db.close()
