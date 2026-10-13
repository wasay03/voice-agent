"""submit_registration: save the confirmed registration. The only tool that writes a patient.

On success, and on a final failure, the closing line is spoken by Vapi verbatim and the call is
ended by the platform (`speak` + `end_call`). In live testing the model sometimes skipped the
"You're all set" line; the brief requires it, so it is no longer left to the model.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.context import ToolContext
from app.agent.speech.phrases.en import SAVE_FAILED, SAVE_RETRY, all_set, reprompt
from app.agent.tools.base import Tool
from app.agent.tools.save_fields import render_errors
from app.domain.enums import SubmitStatus
from app.services.registration_service import RegistrationService

_SAVED = {SubmitStatus.CREATED, SubmitStatus.UPDATED, SubmitStatus.ALREADY_SAVED}


class SubmitRegistrationArgs(BaseModel):
    readback_version: int = Field(description="The readback_version returned by the latest get_readback.")


class SubmitRegistrationTool(Tool):
    name = "submit_registration"
    description = (
        "Save the registration. Call it only after the caller has said yes to every part of the "
        "readback, passing the readback_version from the latest get_readback, and say nothing yourself "
        "in that turn. On success the closing line is spoken for you and the call ends."
    )
    Args = SubmitRegistrationArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: SubmitRegistrationArgs) -> dict[str, Any]:
        result = await self._registration.submit(
            ctx.call_id, args.readback_version, caller_number=ctx.caller_number
        )
        out: dict[str, Any] = {"status": result.status.value, "retryable": result.retryable}

        if result.status in _SAVED and result.patient is not None:
            out["first_name"] = result.patient.first_name
            out["speak"] = all_set(result.patient.first_name)
            out["end_call"] = True
        elif result.status is SubmitStatus.STALE_READBACK:
            out["next"] = "Something changed after the readback. Call get_readback with no part."
        elif result.status is SubmitStatus.READBACK_INCOMPLETE:
            out["next_part"] = result.unread_parts[0]
            out["next"] = (
                "Not every part has been read to the caller yet. "
                f"Call get_readback with part={result.unread_parts[0]!r}."
            )
        elif result.status is SubmitStatus.INVALID:
            out["missing"] = result.missing
            out["errors"] = render_errors(result.errors)
            if result.missing:
                out["say"] = reprompt(result.missing[0], "required")
        elif result.status is SubmitStatus.ERROR:
            if result.retryable:
                out["say"] = SAVE_RETRY
                out["next"] = "Say the line in `say`, then call submit_registration once more."
            else:
                out["speak"] = SAVE_FAILED
                out["end_call"] = True
        return out
