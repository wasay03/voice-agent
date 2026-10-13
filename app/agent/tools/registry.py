"""Tool lookup and the one place where every failure becomes a spoken-friendly result.

`execute` never raises: an unknown tool, bad arguments, a timeout or a bug all come back as a
small dict with an `error` code and a `say` line, because a webhook that errors means the caller
hears silence.
"""

import time
from typing import Any

from pydantic import ValidationError

from app.agent.context import ToolContext
from app.agent.speech.phrases.en import TOOL_TROUBLE
from app.agent.tools.base import Tool
from app.core.logging import get_logger
from app.utils.timeouts import run_with_timeout

log = get_logger(__name__)


class ToolRegistry:
    def __init__(self, tools: list[Tool], *, timeout_seconds: float = 5.0) -> None:
        self._tools = {t.name: t for t in tools}
        self._timeout = timeout_seconds

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def definitions(self) -> list[dict[str, Any]]:
        """Function definitions for the Vapi assistant; scripts/sync_assistant.py publishes these."""
        return [t.definition() for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        started = time.perf_counter()
        outcome = "ok"
        try:
            tool = self._tools.get(name)
            if tool is None:
                outcome = "unknown_tool"
                return {"error": "unknown_tool", "say": TOOL_TROUBLE}
            try:
                args = tool.Args.model_validate(arguments)
            except ValidationError as exc:
                outcome = "invalid_arguments"
                problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
                return {"error": "invalid_arguments", "details": problems, "say": TOOL_TROUBLE}
            result = await run_with_timeout(tool.run(ctx, args), self._timeout)
            outcome = str(result.get("error") or result.get("status") or "ok")
            return result
        except TimeoutError:
            outcome = "timeout"
            return {"error": "timeout", "say": TOOL_TROUBLE}
        except Exception:
            outcome = "exception"
            log.exception("tool.exception", tool=name)
            return {"error": "internal_error", "say": TOOL_TROUBLE}
        finally:
            log.info(
                "tool.called",
                tool=name,
                fields=sorted(arguments.get("fields", {}))
                if isinstance(arguments.get("fields"), dict)
                else None,
                outcome=outcome,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
