"""Calls linked to a patient: transcript, summary and outcome of each registration call."""

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import ContainerDep, PatientServiceDep, require_api_key
from app.api.envelope import Envelope, ok
from app.domain.entities import CallSummary

router = APIRouter(prefix="/patients", tags=["calls"], dependencies=[Depends(require_api_key)])


@router.get(
    "/{patient_id}/calls",
    response_model=Envelope[list[CallSummary]],
    summary="List the calls that created or updated a patient",
    description="Newest first. Each entry has the call's status, ended reason, summary, transcript "
    "and recording URL.",
)
async def list_patient_calls(
    patient_id: UUID, patients: PatientServiceDep, container: ContainerDep
) -> JSONResponse:
    await patients.get(patient_id)  # 404 for a missing or soft-deleted patient
    return ok(await container.calls.calls_for_patient(patient_id))
