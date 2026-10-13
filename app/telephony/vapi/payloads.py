"""The subset of Vapi server messages this service reads.

Shapes follow Vapi's OpenAPI spec (api.vapi.ai/api-json) and docs. Parsing is deliberately
tolerant: a tool call may arrive as `{id, name, parameters}` or `{id, type, function: {name,
arguments}}`, and `arguments` may be a dict or a JSON string. Unknown fields are ignored.
"""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class VapiCustomer(_Lenient):
    number: str | None = None


class VapiCall(_Lenient):
    id: str | None = None
    customer: VapiCustomer | None = None


class VapiMessage(_Lenient):
    """Fields common to every server message we handle."""

    type: str
    call: VapiCall | None = None
    customer: VapiCustomer | None = None

    @property
    def call_id(self) -> str | None:
        return self.call.id if self.call else None

    @property
    def caller_number(self) -> str | None:
        for source in (self.call.customer if self.call else None, self.customer):
            if source and source.number:
                return source.number
        return None


class StatusUpdate(VapiMessage):
    status: str | None = None


class _Artifact(_Lenient):
    transcript: str | None = None
    recordingUrl: str | None = None
    recording: dict[str, Any] | None = None


class _Analysis(_Lenient):
    summary: str | None = None


class EndOfCallReport(VapiMessage):
    endedReason: str | None = None
    artifact: _Artifact | None = None
    analysis: _Analysis | None = None

    @property
    def recording_url(self) -> str | None:
        if self.artifact is None:
            return None
        if self.artifact.recordingUrl:
            return self.artifact.recordingUrl
        recording = self.artifact.recording or {}
        for key in ("url", "stereoUrl", "mono", "combinedUrl"):
            value = recording.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict) and isinstance(value.get("combinedUrl"), str):
                return value["combinedUrl"]
        return None


@dataclass(frozen=True)
class ToolInvocation:
    id: str
    name: str
    arguments: dict[str, Any]


def _arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _invocation(raw: Any) -> ToolInvocation | None:
    if not isinstance(raw, dict):
        return None
    function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
    name = raw.get("name") or function.get("name")
    call_id = raw.get("id")
    if not name or not call_id:
        return None
    arguments = raw.get("parameters")
    if arguments is None:
        arguments = raw.get("arguments", function.get("arguments"))
    return ToolInvocation(id=str(call_id), name=str(name), arguments=_arguments(arguments))


def tool_invocations(message: dict[str, Any]) -> list[ToolInvocation]:
    """The tool calls in a `tool-calls` message, from `toolCallList` or, failing that,
    `toolWithToolCallList[].toolCall`."""
    candidates = message.get("toolCallList") or [
        entry.get("toolCall")
        for entry in message.get("toolWithToolCallList") or []
        if isinstance(entry, dict)
    ]
    found = [_invocation(c) for c in candidates or []]
    return [i for i in found if i is not None]
