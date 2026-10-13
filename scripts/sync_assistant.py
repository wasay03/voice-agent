#!/usr/bin/env python
"""Create or update the Vapi assistant from assistant/ (prompt, config, tool schemas).

    python scripts/sync_assistant.py --env dev            # create/update ava-dev
    python scripts/sync_assistant.py --env prod --diff    # show what would change, push nothing
    python scripts/sync_assistant.py --env prod           # diff, confirm, push, attach the number

Everything is idempotent: the assistant is found by name and updated in place. The prod run
also points VAPI_PHONE_NUMBER_ID at the assistant.
"""

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent.tools import build_registry  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.services.registration_service import RegistrationService  # noqa: E402

ASSISTANT_DIR = ROOT / "assistant"
VAPI = "https://api.vapi.ai"
_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def substitute(text: str, values: dict[str, str]) -> str:
    """Replace ${VAR}; an unknown variable is an error rather than a silently broken prompt."""

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise SystemExit(f"unknown variable ${{{name}}} in assistant config")
        return values[name]

    return _VAR.sub(repl, text)


def strip_comments(text: str) -> str:
    kept = [line for line in text.splitlines() if not line.lstrip().startswith("//")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() + "\n"


def walk(value: Any, values: dict[str, str]) -> Any:
    if isinstance(value, str):
        return substitute(value, values)
    if isinstance(value, list):
        return [walk(v, values) for v in value]
    if isinstance(value, dict):
        return {k: walk(v, values) for k, v in value.items()}
    return value


def build_payload(env: str) -> tuple[dict[str, Any], dict[str, Any]]:
    settings = get_settings()
    if not settings.public_base_url:
        raise SystemExit("PUBLIC_BASE_URL is not set (the deployed service URL, or an ngrok URL for dev)")
    values = {
        "AGENT_NAME": settings.agent_name,
        "CLINIC_NAME": settings.clinic_name,
        "CLINIC_TZ": settings.clinic_tz,
        "PUBLIC_BASE_URL": settings.public_base_url.rstrip("/"),
        "VAPI_WEBHOOK_SECRET": settings.vapi_webhook_secret.get_secret_value(),
    }
    config = yaml.safe_load((ASSISTANT_DIR / "assistant.yaml").read_text())
    environment = yaml.safe_load((ASSISTANT_DIR / "environments.yaml").read_text())[env]
    tool_messages = config.pop("tool_messages", {})
    config = walk(config, values)
    tool_messages = walk(tool_messages, values)

    system_prompt = substitute(
        strip_comments((ASSISTANT_DIR / "prompts/system_prompt.md").read_text()), values
    )
    first_message = substitute((ASSISTANT_DIR / "prompts/first_message.md").read_text().strip(), values)

    server = config["server"]
    registry = build_registry(cast(RegistrationService, None))
    tools = []
    for definition in registry.definitions():
        name = definition["function"]["name"]
        tools.append(
            {
                **definition,
                "server": server,
                "messages": tool_messages.get(name, tool_messages.get("default", [])),
            }
        )
    tools.append({"type": "endCall"})

    model = {
        **config.pop("model"),
        "messages": [{"role": "system", "content": system_prompt}],
        "tools": tools,
    }
    payload = {
        "name": environment["name"],
        "firstMessage": first_message,
        **config,
        "model": model,
        "metadata": {**config.get("metadata", {}), "environment": env},
    }
    return payload, environment


def find_by_name(client: httpx.Client, name: str) -> dict[str, Any] | None:
    response = client.get("/assistant", params={"limit": 100})
    response.raise_for_status()
    return next((a for a in response.json() if a.get("name") == name), None)


def comparable(assistant: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str]:
    """The live assistant restricted to the keys we manage, as two JSON texts to diff."""
    live = {k: assistant.get(k) for k in payload}
    return (
        json.dumps(live, indent=2, sort_keys=True, default=str),
        json.dumps(payload, indent=2, sort_keys=True, default=str),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env", choices=["dev", "prod"], required=True)
    parser.add_argument("--diff", action="store_true", help="show the change and exit without pushing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation for prod")
    args = parser.parse_args()

    settings = get_settings()
    if settings.vapi_api_key is None:
        raise SystemExit("VAPI_API_KEY is not set")
    payload, environment = build_payload(args.env)

    headers = {"Authorization": f"Bearer {settings.vapi_api_key.get_secret_value()}"}
    with httpx.Client(base_url=VAPI, headers=headers, timeout=30) as client:
        existing = find_by_name(client, payload["name"])
        if existing is None:
            print(f"assistant {payload['name']!r} does not exist yet; it will be created")
        else:
            before, after = comparable(existing, payload)
            diff = list(
                difflib.unified_diff(before.splitlines(), after.splitlines(), "live", "new", lineterm="", n=2)
            )
            print(
                f"assistant {payload['name']!r} ({existing['id']}): "
                + ("no changes" if not diff else "changes:")
            )
            print("\n".join(diff))
        if args.diff:
            return 0
        needs_confirmation = environment.get("confirm") and not args.yes and existing is not None
        if needs_confirmation and input("push to production? [y/N] ").strip().lower() != "y":
            print("aborted")
            return 1

        if existing is None:
            response = client.post("/assistant", json=payload)
        else:
            response = client.patch(f"/assistant/{existing['id']}", json=payload)
        if response.status_code >= 400:
            print(f"Vapi rejected the assistant: {response.status_code} {response.text}", file=sys.stderr)
            return 1
        assistant = response.json()
        verb = "created" if existing is None else "updated"
        print(f"{verb} assistant {assistant['name']} id={assistant['id']}")

        if environment.get("attach_phone_number"):
            number_id = settings.vapi_phone_number_id or os.environ.get("VAPI_PHONE_NUMBER_ID")
            if not number_id:
                raise SystemExit("VAPI_PHONE_NUMBER_ID is not set")
            attach = client.patch(f"/phone-number/{number_id}", json={"assistantId": assistant["id"]})
            if attach.status_code >= 400:
                print(
                    f"could not attach the phone number: {attach.status_code} {attach.text}", file=sys.stderr
                )
                return 1
            print(f"phone number {attach.json().get('number')} now answers with {assistant['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
