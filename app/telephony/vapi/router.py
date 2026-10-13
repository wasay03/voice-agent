"""POST /webhooks/vapi — the single entry point Vapi calls during a conversation."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.deps import ContainerDep
from app.core.errors import BadRequestError
from app.core.logging import get_logger
from app.telephony.vapi.auth import verify_webhook

log = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"], dependencies=[Depends(verify_webhook)])


@router.post("/vapi", include_in_schema=False)
async def vapi_webhook(request: Request, container: ContainerDep) -> JSONResponse:
    try:
        body: Any = await request.json()
    except ValueError:
        raise BadRequestError("Webhook body is not valid JSON.") from None
    if not isinstance(body, dict):
        raise BadRequestError("Webhook body must be a JSON object.")
    try:
        response = await container.vapi.dispatch(body)
    except Exception:
        # Bookkeeping messages must not make Vapi think the server is down; the log has the detail.
        log.exception("vapi.dispatch_failed", message_type=(body.get("message") or {}).get("type"))
        response = {}
    return JSONResponse(response)
