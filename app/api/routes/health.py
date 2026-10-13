"""Liveness (`/healthz`, no DB, used by keep-alive pings) and readiness (`/health`, pings the DB)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import ContainerDep
from app.api.envelope import fail, ok

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness: the process is up (does not touch the database)")
async def healthz() -> JSONResponse:
    return ok({"status": "ok"})


@router.get("/health", summary="Readiness: the process is up and the database answers")
async def health(container: ContainerDep) -> JSONResponse:
    if await container.db.ping():
        return ok({"status": "ok", "db": "ok"})
    return fail(
        503,
        "database_unavailable",
        "The database is not reachable.",
        data={"status": "degraded", "db": "unreachable"},
    )
