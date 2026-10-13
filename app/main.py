"""Application factory. Run with: uvicorn --factory app.main:create_app"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import request_context
from app.api.routes import health, patients
from app.container import Container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.domain import clock
from app.telephony.vapi.router import router as vapi_router

log = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_logs=settings.json_logs)
    clock.configure(settings.clinic_tz)
    container = Container.build(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await container.start()
        app.state.container = container
        log.info("app.started", env=settings.env)
        try:
            yield
        finally:
            await container.stop()

    app = FastAPI(
        title="Patient Registration Voice Agent API",
        version="0.1.0",
        description="REST API and Vapi webhook for the voice patient-registration agent.",
        lifespan=lifespan,
    )
    app.middleware("http")(request_context)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(patients.router)
    app.include_router(vapi_router)
    return app
