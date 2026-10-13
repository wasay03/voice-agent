"""The five patient endpoints from the brief. Routing and HTTP shape only; rules live in the
domain schemas and the service."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PatientServiceDep, require_api_key
from app.api.envelope import Envelope, ok
from app.domain.schemas import PatientCreate, PatientFilters, PatientOut, PatientUpdate

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(require_api_key)])


@router.get(
    "",
    response_model=Envelope[list[PatientOut]],
    summary="List patients",
    description="Optional filters: `last_name` (case-insensitive exact), `date_of_birth` (MM/DD/YYYY or "
    "YYYY-MM-DD), `phone_number` (any formatting). Paged with `limit` (1–200, default 50) and "
    "`offset`; the total number of matches is in the `X-Total-Count` header.",
)
async def list_patients(
    filters: Annotated[PatientFilters, Query()], service: PatientServiceDep
) -> JSONResponse:
    page = await service.search(filters)
    return ok(page.items, headers={"X-Total-Count": str(page.total)})


@router.get("/{patient_id}", response_model=Envelope[PatientOut], summary="Get one patient")
async def get_patient(patient_id: UUID, service: PatientServiceDep) -> JSONResponse:
    return ok(await service.get(patient_id))


@router.post("", status_code=201, response_model=Envelope[PatientOut], summary="Create a patient")
async def create_patient(body: PatientCreate, service: PatientServiceDep, request: Request) -> JSONResponse:
    patient = await service.create(body)
    location = str(request.url_for("get_patient", patient_id=patient.patient_id))
    return ok(patient, status_code=201, headers={"Location": location})


@router.put(
    "/{patient_id}",
    response_model=Envelope[PatientOut],
    summary="Update a patient (partial)",
    description="Only the fields in the body change. Required fields cannot be set to null.",
)
async def update_patient(patient_id: UUID, body: PatientUpdate, service: PatientServiceDep) -> JSONResponse:
    return ok(await service.update(patient_id, body))


@router.delete(
    "/{patient_id}",
    response_model=Envelope[PatientOut],
    summary="Soft-delete a patient",
    description="Sets `deleted_at`; the record disappears from every read but is not removed.",
)
async def delete_patient(patient_id: UUID, service: PatientServiceDep) -> JSONResponse:
    return ok(await service.delete(patient_id))
