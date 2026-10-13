"""reset_registration: the caller asked to start over."""

from typing import Any

from pydantic import BaseModel

from app.agent.context import ToolContext
from app.agent.tools.base import Tool
from app.services.registration_service import RegistrationService


class ResetRegistrationArgs(BaseModel):
    pass


class ResetRegistrationTool(Tool):
    name = "reset_registration"
    description = (
        "Clear everything collected so far and start the registration over. Confirm with the caller "
        "once before calling it, then begin again with their name."
    )
    Args = ResetRegistrationArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: ResetRegistrationArgs) -> dict[str, Any]:
        result = await self._registration.reset(ctx.call_id, caller_number=ctx.caller_number)
        if not result.cleared:
            return {
                "cleared": False,
                "say": "That registration has already been saved, so I can't start it over on this call.",
            }
        return {"cleared": True}
