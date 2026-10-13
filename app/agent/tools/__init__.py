"""The agent's tools and the registry that runs them."""

from app.agent.tools.get_readback import GetReadbackTool
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.reset_registration import ResetRegistrationTool
from app.agent.tools.save_fields import SaveFieldsTool
from app.agent.tools.submit_registration import SubmitRegistrationTool
from app.agent.tools.switch_to_update import SwitchToUpdateTool
from app.services.registration_service import RegistrationService


def build_registry(registration: RegistrationService, *, timeout_seconds: float = 5.0) -> ToolRegistry:
    return ToolRegistry(
        [
            SaveFieldsTool(registration),
            SwitchToUpdateTool(registration),
            GetReadbackTool(registration),
            SubmitRegistrationTool(registration),
            ResetRegistrationTool(registration),
        ],
        timeout_seconds=timeout_seconds,
    )


__all__ = ["ToolRegistry", "build_registry"]
