"""FastAPI dependencies: auth and access to the container's long-lived objects."""

from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader

from app.container import Container
from app.core.errors import AuthenticationError
from app.core.security import secret_matches
from app.services.patient_service import PatientService

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


def require_api_key(container: ContainerDep, api_key: str | None = Security(_api_key_header)) -> None:
    if not secret_matches(api_key, container.settings.api_key):
        raise AuthenticationError("Missing or invalid X-API-Key header.")


def get_patient_service(container: ContainerDep) -> PatientService:
    return container.patients


PatientServiceDep = Annotated[PatientService, Depends(get_patient_service)]
