"""Route a Vapi server message to the right handler and build Vapi's expected response.

Only `tool-calls` needs a meaningful answer (and always gets HTTP 200 with `results`, even when a
tool fails: an error response would leave the caller in silence). The other messages are
bookkeeping and are acknowledged with an empty object.
"""

import json
from typing import Any

import structlog

from app.agent.context import ToolContext
from app.agent.tools.registry import ToolRegistry
from app.core.logging import get_logger
from app.services.call_log_service import CallLogService
from app.telephony.vapi.payloads import EndOfCallReport, StatusUpdate, VapiMessage, tool_invocations

log = get_logger(__name__)

# Spoken by the agent when we cannot even identify the call; the model sees it as the result.
_NO_CALL_ID = json.dumps(
    {"error": "no_call_id", "say": "Sorry, I had a little trouble with that. Could you say that again?"}
)


class VapiDispatcher:
    def __init__(self, tools: ToolRegistry, calls: CallLogService) -> None:
        self._tools = tools
        self._calls = calls

    async def dispatch(self, body: dict[str, Any]) -> dict[str, Any]:
        raw = body.get("message")
        if not isinstance(raw, dict):
            log.warning("vapi.malformed_message")
            return {}
        message = VapiMessage.model_validate(raw)
        if message.call_id:
            structlog.contextvars.bind_contextvars(call_id=message.call_id)

        match message.type:
            case "tool-calls":
                return await self._tool_calls(raw, message)
            case "status-update":
                await self._status_update(StatusUpdate.model_validate(raw))
            case "end-of-call-report":
                await self._end_of_call(EndOfCallReport.model_validate(raw))
            case "hang":
                log.warning("vapi.hang", detail="assistant did not respond in time")
            case other:
                log.debug("vapi.ignored", type=other)
        return {}

    async def _tool_calls(self, raw: dict[str, Any], message: VapiMessage) -> dict[str, Any]:
        results = []
        ctx = (
            ToolContext(call_id=message.call_id, caller_number=message.caller_number)
            if message.call_id
            else None
        )
        # In order, never concurrently: the model may emit several calls that touch one draft.
        for invocation in tool_invocations(raw):
            entry: dict[str, Any] = {"name": invocation.name, "toolCallId": invocation.id}
            if ctx is None:
                entry["result"] = _NO_CALL_ID
            else:
                result = await self._tools.execute(invocation.name, invocation.arguments, ctx)
                entry["result"] = json.dumps(result, default=str)
                # `speak` is said verbatim by Vapi instead of a model-generated reply. It stays in
                # the result too, so the model knows exactly what the caller just heard.
                if isinstance(result.get("speak"), str):
                    entry["message"] = {"type": "request-complete", "content": result["speak"]}
            results.append(entry)
        return {"results": results}

    async def _status_update(self, message: StatusUpdate) -> None:
        if message.call_id and message.status == "in-progress":
            await self._calls.start(message.call_id, message.caller_number)

    async def _end_of_call(self, report: EndOfCallReport) -> None:
        if not report.call_id:
            log.warning("vapi.end_of_call_without_call_id")
            return
        await self._calls.end(
            report.call_id,
            ended_reason=report.endedReason,
            transcript=report.artifact.transcript if report.artifact else None,
            summary=report.analysis.summary if report.analysis else None,
            recording_url=report.recording_url,
            caller_number=report.caller_number,
        )
