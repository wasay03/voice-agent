"""Tool definitions must satisfy Vapi's validator: every property has a plain JSON `type`."""

from typing import Any, cast

from app.agent.tools import build_registry
from app.services.registration_service import RegistrationService

ALLOWED = {"string", "number", "integer", "boolean", "array", "object", "null"}


def _walk(schema: dict[str, Any], path: str) -> None:
    for name, prop in schema.get("properties", {}).items():
        where = f"{path}.{name}"
        assert prop.get("type") in ALLOWED, f"{where} has no plain type: {prop}"
        assert "anyOf" not in prop and "oneOf" not in prop, where
        _walk(prop, where)


def test_every_tool_schema_uses_plain_types() -> None:
    registry = build_registry(cast(RegistrationService, None))
    assert registry.names == [
        "save_fields",
        "switch_to_update",
        "get_readback",
        "submit_registration",
        "reset_registration",
    ]
    for definition in registry.definitions():
        function = definition["function"]
        assert function["parameters"]["type"] == "object"
        _walk(function["parameters"], function["name"])


def test_optional_readback_part_is_a_plain_optional_string() -> None:
    registry = build_registry(cast(RegistrationService, None))
    readback = next(d for d in registry.definitions() if d["function"]["name"] == "get_readback")
    params = readback["function"]["parameters"]
    assert params["properties"]["part"]["type"] == "string"
    assert "part" not in params.get("required", [])
