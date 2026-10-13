"""Patient use cases behind the REST API. Business logic only: data access goes through the
unit of work, validation through the domain schemas."""

from dataclasses import dataclass
from uuid import UUID

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db.unit_of_work import UnitOfWork
from app.domain.schemas import PatientCreate, PatientFilters, PatientOut, PatientUpdate

log = get_logger(__name__)


@dataclass(frozen=True)
class PatientPage:
    items: list[PatientOut]
    total: int


def _not_found(patient_id: UUID) -> NotFoundError:
    return NotFoundError(f"Patient {patient_id} was not found.")


class PatientService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(self, data: PatientCreate) -> PatientOut:
        async with self._uow() as repos:
            patient = await repos.patients.create(data)
        log.info("patient.created", patient_id=str(patient.patient_id))
        return patient

    async def get(self, patient_id: UUID) -> PatientOut:
        async with self._uow(transactional=False) as repos:
            patient = await repos.patients.get_by_id(patient_id)
        if patient is None:
            raise _not_found(patient_id)
        return patient

    async def search(self, filters: PatientFilters) -> PatientPage:
        async with self._uow(transactional=False) as repos:
            items, total = await repos.patients.search(filters)
        return PatientPage(items=items, total=total)

    async def update(self, patient_id: UUID, data: PatientUpdate) -> PatientOut:
        changes = data.changes()
        async with self._uow() as repos:
            patient = await repos.patients.update(patient_id, changes)
        if patient is None:
            raise _not_found(patient_id)
        log.info("patient.updated", patient_id=str(patient_id), fields=sorted(changes))
        return patient

    async def delete(self, patient_id: UUID) -> PatientOut:
        async with self._uow() as repos:
            patient = await repos.patients.soft_delete(patient_id)
        if patient is None:
            raise _not_found(patient_id)
        log.info("patient.deleted", patient_id=str(patient_id))
        return patient
