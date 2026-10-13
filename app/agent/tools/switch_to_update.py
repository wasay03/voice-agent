"""switch_to_update: the caller confirmed they are an existing patient; update that record."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.agent.context import ToolContext
from app.agent.tools.base import Tool
from app.services.registration_service import RegistrationService


class SwitchToUpdateArgs(BaseModel):
    patient_id: UUID = Field(description="The patient_id from existing_patients that the caller confirmed.")


class SwitchToUpdateTool(Tool):
    name = "switch_to_update"
    description = (
        "Call this when save_fields returned existing_patients and the caller confirmed they are that "
        "person and want to update their information. Loads the existing record into the registration."
    )
    Args = SwitchToUpdateArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    async def run(self, ctx: ToolContext, args: SwitchToUpdateArgs) -> dict[str, Any]:
        result = await self._registration.switch_to_update(
            ctx.call_id, args.patient_id, caller_number=ctx.caller_number
        )
        if not result.switched:
            return {
                "switched": False,
                "say": "I wasn't able to pull up that record, so let's continue as a new registration.",
            }
        return {"switched": True, "fields": result.draft, "next_missing": result.next_missing}
