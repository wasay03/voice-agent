"""The tool contract: a name, a description, typed arguments, and a handler returning a small dict.

Tool arguments never include the call id: it comes from the webhook's call object, so the model
cannot read or write another caller's session.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from app.agent.context import ToolContext


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    Args: ClassVar[type[BaseModel]]

    @abstractmethod
    async def run(self, ctx: ToolContext, args: Any) -> dict[str, Any]:
        """Return a JSON-serialisable dict. Expected problems are results, not exceptions."""

    def parameters(self) -> dict[str, Any]:
        """JSON Schema of the arguments, as sent to the LLM."""
        schema = self.Args.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        return schema

    def definition(self) -> dict[str, Any]:
        """The OpenAI-style function definition Vapi attaches to the assistant's model."""
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters()},
        }
