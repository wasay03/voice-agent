"""submit_registration: save the confirmed registration. The only tool that writes a patient."""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.context import ToolContext
from app.agent.speech.phrases.en import SAVE_FAILED, reprompt
from app.agent.tools.base import Tool
from app.agent.tools.save_fields import render_errors
from app.domain.enums import SubmitStatus
from app.services.registration_service import RegistrationService


class SubmitRegistrationArgs(BaseModel):
    readback_version: int = Field(description="The readback_version returned by the latest get_readback.")


class SubmitRegistrationTool(Tool):
    name = "submit_registration"
    description = (
        "Save the registration. Call it only after the caller has said yes to every readback chunk, "
        "passing the readback_version from the latest get_readback. Never tell the caller it is saved "
        "unless the status is created, updated or already_saved."
    )
    Args = SubmitRegistrationArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: SubmitRegistrationArgs) -> dict[str, Any]:
        result = await self._registration.submit(
            ctx.call_id, args.readback_version, caller_number=ctx.caller_number
        )
        out: dict[str, Any] = {"status": result.status.value, "retryable": result.retryable}
        if result.patient is not None:
            out["first_name"] = result.patient.first_name
            out["say"] = f"You're all set, {result.patient.first_name}."
        if result.status is SubmitStatus.STALE_READBACK:
            out["say"] = "Something changed after I read that back. Let me read the updated details."
        elif result.status is SubmitStatus.INVALID:
            out["missing"] = result.missing
            out["errors"] = render_errors(result.errors)
            if result.missing:
                out["say"] = reprompt(result.missing[0], "required")
        elif result.status is SubmitStatus.ERROR:
            out["say"] = SAVE_FAILED
        return out
