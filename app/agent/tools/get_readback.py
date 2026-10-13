"""get_readback: confirm the draft with the caller, one part at a time.

Each part is spoken by Vapi verbatim (the `speak` key becomes the tool result's
`request-complete` message), not by the model. In the first live test the model paraphrased
the first part down to the name only, so the date of birth, sex and phone were never confirmed.
Speaking the server's text directly makes "what the caller heard" and "what gets saved" the same
thing by construction, and the server refuses to save until every part has been read.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.context import ToolContext
from app.agent.speech.readback import render_readback
from app.agent.tools.base import Tool
from app.services.registration_service import RegistrationService

CONFIRM_QUESTION = "Is that all correct?"


def _next_step(remaining: list[str]) -> dict[str, Any]:
    if remaining:
        return {
            "next_part": remaining[0],
            "next": f"When the caller says yes, call get_readback with part={remaining[0]!r}.",
        }
    return {"next_part": None, "next": "When the caller says yes, call submit_registration."}


class GetReadbackArgs(BaseModel):
    part: str | None = Field(
        default=None,
        description="Leave empty to start the readback, or after a correction. To read the next part, "
        "pass `next_part` from the previous get_readback result.",
    )


class GetReadbackTool(Tool):
    name = "get_readback"
    description = (
        "Read the collected details back to the caller for confirmation. The text is spoken for you, "
        "exactly as written, followed by 'Is that all correct?'. Do not repeat or paraphrase it, and say "
        "nothing yourself in the turn where you call this tool. Call it with no part when next_missing "
        "is empty and the optional-information offer has been answered, and again with no part after "
        "any correction. Follow `next` in the result for what to do once the caller says yes."
    )
    Args = GetReadbackArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: GetReadbackArgs) -> dict[str, Any]:
        if args.part:
            part = await self._registration.readback_part(
                ctx.call_id, args.part, caller_number=ctx.caller_number
            )
            if part is None:
                return {"error": "readback_outdated", "next": "Call get_readback with no part."}
            return {
                "part": part.chunk.key,
                "speak": f"{part.chunk.text} {CONFIRM_QUESTION}",
                **_next_step(part.remaining_keys),
            }

        result = await self._registration.get_readback(
            ctx.call_id, render_readback, language=ctx.language, caller_number=ctx.caller_number
        )
        if not result.ready or result.delivering is None:
            return {"ready": False, "missing": result.missing}
        return {
            "ready": True,
            "readback_version": result.readback_version,
            "part": result.delivering.key,
            "speak": f"{result.delivering.text} {CONFIRM_QUESTION}",
            **_next_step(result.remaining_keys),
        }
