"""Composition root: builds long-lived objects once and hands them to the app."""

from dataclasses import dataclass

from app.core.config import Settings
from app.db.client import DatabaseClient
from app.db.unit_of_work import UnitOfWork
from app.services.call_log_service import CallLogService
from app.services.patient_service import PatientService
from app.services.registration_service import RegistrationService


@dataclass
class Container:
    settings: Settings
    db: DatabaseClient
    patients: PatientService
    registration: RegistrationService
    calls: CallLogService

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
        return cls(
            settings=settings,
            db=db,
            patients=PatientService(uow),
            registration=RegistrationService(uow, tool_timeout_seconds=settings.tool_timeout_seconds),
            calls=CallLogService(uow),
        )

    async def start(self) -> None:
        await self.db.connect()

    async def stop(self) -> None:
        await self.db.close()
