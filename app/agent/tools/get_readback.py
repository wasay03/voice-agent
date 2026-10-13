"""get_readback: confirm the draft with the caller, one chunk at a time.

The chunk is spoken by Vapi verbatim (the `speak` key becomes the tool result's
`request-complete` message), not by the model. In the first live test the model paraphrased
the first chunk down to the name only, so the date of birth, sex and phone were never confirmed.
Speaking the server's text directly makes "what the caller confirmed" and "what gets saved" the
same thing by construction.
"""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.context import ToolContext
from app.agent.speech.readback import render_readback
from app.agent.tools.base import Tool
from app.services.registration_service import RegistrationService

CONFIRM_QUESTION = "Is that all correct?"


class GetReadbackArgs(BaseModel):
    part: str | None = Field(
        default=None,
        description="Leave empty to start the readback. To read the next part, pass the next key "
        "from `parts` of the previous get_readback result.",
    )


class GetReadbackTool(Tool):
    name = "get_readback"
    description = (
        "Read the collected details back to the caller for confirmation. The text is spoken for you, "
        "exactly as written, followed by 'Is that all correct?'; do not repeat or paraphrase it, and say "
        "nothing before calling this tool. Call it with no part when next_missing is empty and the "
        "optional-information offer has been answered, and again with no part after any correction. "
        "If `parts` lists more than one key, call it again with the next key once the caller says yes."
    )
    Args = GetReadbackArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: GetReadbackArgs) -> dict[str, Any]:
        if args.part:
            chunk = await self._registration.readback_part(
                ctx.call_id, args.part, caller_number=ctx.caller_number
            )
            if chunk is None:
                return {"error": "readback_outdated", "next": "call get_readback with no part"}
            return {"part": chunk.key, "speak": f"{chunk.text} {CONFIRM_QUESTION}"}

        result = await self._registration.get_readback(
            ctx.call_id, render_readback, language=ctx.language, caller_number=ctx.caller_number
        )
        if not result.ready:
            return {"ready": False, "missing": result.missing}
        # After a correction only the chunks whose text changed need confirming again.
        keys = result.changed_keys or [c.key for c in result.chunks]
        first = next(c for c in result.chunks if c.key == keys[0])
        return {
            "ready": True,
            "readback_version": result.readback_version,
            "parts": keys,
            "speaking": first.key,
            "speak": f"{first.text} {CONFIRM_QUESTION}",
        }
