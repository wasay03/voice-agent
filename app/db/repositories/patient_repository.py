"""Data access for patients. One routine per method; rows are mapped to domain models here."""

from typing import Any
from uuid import UUID

from app.db.repositories.base import BaseRepository
from app.domain.entities import DuplicateCandidate
from app.domain.schemas import PatientCreate, PatientFilters, PatientOut


def _to_patient(record: dict[str, Any] | None) -> PatientOut | None:
    return PatientOut.model_validate(record) if record is not None else None


class PatientRepository(BaseRepository):
    async def get_by_id(self, patient_id: UUID) -> PatientOut | None:
        return _to_patient(await self._fn_value("fn_patient_get_by_id", patient_id))

    async def search(self, filters: PatientFilters) -> tuple[list[PatientOut], int]:
        rows = await self._fn_rows(
            "fn_patient_search",
            filters.last_name,
            filters.date_of_birth,
            filters.phone_number,
            filters.limit,
            filters.offset,
        )
        total = rows[0]["total_count"] if rows else 0
        return [PatientOut.model_validate(r["patient"]) for r in rows], total

    async def find_by_phone(self, phone_number: str) -> list[DuplicateCandidate]:
        rows = await self._fn_rows("fn_patient_find_by_phone", phone_number)
        return [DuplicateCandidate.model_validate(dict(r)) for r in rows]

    async def create(self, p: PatientCreate) -> PatientOut:
        row = await self._sp(
            "sp_patient_create",
            p.first_name,
            p.last_name,
            p.date_of_birth,
            p.sex.value,
            p.phone_number,
            p.email,
            p.address_line_1,
            p.address_line_2,
            p.city,
            p.state,
            p.zip_code,
            p.insurance_provider,
            p.insurance_member_id,
            p.preferred_language,
            p.emergency_contact_name,
            p.emergency_contact_phone,
            outputs=("jsonb",),
        )
        patient = _to_patient(row["p_record"] if row else None)
        if patient is None:  # the INSERT ... RETURNING always fills it; guard against a broken routine
            raise RuntimeError("sp_patient_create returned no record")
        return patient

    async def update(self, patient_id: UUID, changes: dict[str, Any]) -> PatientOut | None:
        row = await self._sp("sp_patient_update", patient_id, changes, outputs=("jsonb",))
        return _to_patient(row["p_record"] if row else None)

    async def soft_delete(self, patient_id: UUID) -> PatientOut | None:
        row = await self._sp("sp_patient_soft_delete", patient_id, outputs=("jsonb",))
        return _to_patient(row["p_record"] if row else None)
