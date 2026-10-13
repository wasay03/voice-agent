"""get_readback: the server-written confirmation text for the draft, plus the version to submit."""

from typing import Any

from pydantic import BaseModel

from app.agent.context import ToolContext
from app.agent.speech.readback import render_readback
from app.agent.tools.base import Tool
from app.services.registration_service import RegistrationService


class GetReadbackArgs(BaseModel):
    pass


class GetReadbackTool(Tool):
    name = "get_readback"
    description = (
        "Get the text to read back to the caller for confirmation. Call it when next_missing is empty "
        "and the optional-information offer has been answered, and again after any correction. Read the "
        "returned chunks exactly as written, one at a time, asking 'Is that all correct?' after each."
    )
    Args = GetReadbackArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: GetReadbackArgs) -> dict[str, Any]:
        result = await self._registration.get_readback(
            ctx.call_id, render_readback, language=ctx.language, caller_number=ctx.caller_number
        )
        if not result.ready:
            return {"ready": False, "missing": result.missing}
        # After a correction only the chunks whose text changed need reading again.
        to_read = [c for c in result.chunks if c.key in result.changed_keys] or result.chunks
        return {
            "ready": True,
            "chunks": [c.text for c in to_read],
            "readback_version": result.readback_version,
        }
