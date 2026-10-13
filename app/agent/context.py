"""What a tool knows about the call it runs in. Built by the telephony adapter, never by the model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolContext:
    call_id: str
    caller_number: str | None = None
    language: str = "en"
