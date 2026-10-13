"""The Vapi webhook end to end: auth, message shapes, and a whole registration conversation."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.db.unit_of_work import UnitOfWork
from app.domain.enums import CallStatus
from tests.conftest import TEST_API_KEY, TEST_WEBHOOK_SECRET, new_call_id, unique_phone

FIXTURES = Path(__file__).parent / "fixtures"
SECRET = {"X-Vapi-Secret": TEST_WEBHOOK_SECRET}
CALLER = "+15125550123"


def fixture(name: str, call_id: str, caller: str = CALLER) -> dict[str, Any]:
    text = (
        (FIXTURES / f"{name}.json").read_text().replace("{{CALL_ID}}", call_id).replace("{{CALLER}}", caller)
    )
    return json.loads(text)


def tool_call(call_id: str, *calls: tuple[str, dict[str, Any]], caller: str = CALLER) -> dict[str, Any]:
    items = [
        {"id": f"tc_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls)
    ]
    return {
        "message": {
            "type": "tool-calls",
            "call": {"id": call_id, "customer": {"number": caller}},
            "toolCallList": items,
        }
    }


async def post(client: httpx.AsyncClient, body: Any, headers: dict[str, str] | None = None) -> httpx.Response:
    return await client.post("/webhooks/vapi", json=body, headers=SECRET if headers is None else headers)


async def tools(client: httpx.AsyncClient, call_id: str, *calls: tuple[str, dict[str, Any]]) -> list[dict]:
    response = await post(client, tool_call(call_id, *calls))
    assert response.status_code == 200
    return [json.loads(r["result"]) for r in response.json()["results"]]


async def test_secret_is_required(client: httpx.AsyncClient) -> None:
    body = fixture("hang", new_call_id())
    assert (await post(client, body, headers={})).status_code == 401
    assert (await post(client, body, headers={"X-Vapi-Secret": "nope"})).status_code == 401
    assert (
        await post(client, body, headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"})
    ).status_code == 200
    assert (await post(client, body)).status_code == 200


async def test_unreadable_bodies_are_400(client: httpx.AsyncClient) -> None:
    bad = await client.post(
        "/webhooks/vapi", content=b"{nope", headers={**SECRET, "Content-Type": "application/json"}
    )
    assert bad.status_code == 400
    assert (await post(client, ["not", "an", "object"])).status_code == 400
    assert (await post(client, {"message": "text"})).json() == {}


async def test_status_update_creates_the_session_with_the_caller_number(
    client: httpx.AsyncClient, uow: UnitOfWork
) -> None:
    call_id = new_call_id()
    response = await post(client, fixture("status_update_in_progress", call_id))
    assert response.status_code == 200
    async with uow(transactional=False) as repos:
        session = await repos.call_sessions.get(call_id)
    assert session is not None
    assert (session.caller_number, session.status) == (CALLER, CallStatus.IN_PROGRESS)


@pytest.mark.parametrize("shape", ["tool_calls_function_shape", "tool_calls_flat_shape"])
async def test_both_tool_call_shapes_are_understood(client: httpx.AsyncClient, shape: str) -> None:
    response = await post(client, fixture(shape, new_call_id()))
    assert response.status_code == 200
    (result,) = response.json()["results"]
    assert result["toolCallId"] in {"call_abc123", "call_flat_1"}
    assert result["name"] == "save_fields"
    payload = json.loads(result["result"])  # Vapi requires the result as a string
    assert payload["errors"] == [] and payload["saved"]


async def test_a_whole_registration_through_the_webhook(client: httpx.AsyncClient, uow: UnitOfWork) -> None:
    call_id, phone = new_call_id(), unique_phone()
    assert (await post(client, fixture("status_update_in_progress", call_id))).status_code == 200

    # First turn: three answers at once, one of them invalid.
    (first,) = await tools(
        client,
        call_id,
        (
            "save_fields",
            {"fields": {"first_name": "jane", "last_name": "Davies", "date_of_birth": "2999-01-01"}},
        ),
    )
    assert first["saved"] == ["first_name", "last_name"]
    assert first["errors"][0]["field"] == "date_of_birth"
    assert "future" in first["errors"][0]["say"]
    assert first["next_missing"][0] == "date_of_birth"

    # Two tool calls in one message are applied in order; null must not clear anything.
    saved, corrected = await tools(
        client,
        call_id,
        (
            "save_fields",
            {
                "fields": {
                    "date_of_birth": "1980-03-05",
                    "sex": "female",
                    "phone_number": phone,
                    "first_name": None,
                    "address_line_1": "1200 Barton Springs Rd",
                    "city": "austin",
                    "state": "texas",
                    "zip_code": "78704",
                }
            },
        ),
        ("save_fields", {"fields": {"last_name": "Davis"}}),  # "D-A-V-I-S, not D-A-V-I-E-S"
    )
    assert saved["errors"] == [] and saved["next_missing"] == []
    assert corrected["saved"] == ["last_name"]

    (readback,) = await tools(client, call_id, ("get_readback", {}))
    assert readback["ready"] is True
    assert "D-A-V-I-S" in readback["chunks"][0] and "Jane Davis" in readback["chunks"][0]

    (done,) = await tools(
        client, call_id, ("submit_registration", {"readback_version": readback["readback_version"]})
    )
    assert done["status"] == "created"
    assert done["say"] == "You're all set, Jane."

    report = await post(client, fixture("end_of_call_report", call_id))
    assert report.status_code == 200

    # The record is retrievable through the REST API, and the call is linked to it.
    listed = await client.get(
        "/patients", params={"phone_number": phone}, headers={"X-API-Key": TEST_API_KEY}
    )
    (patient,) = listed.json()["data"]
    assert (patient["first_name"], patient["last_name"], patient["state"]) == ("Jane", "Davis", "TX")
    async with uow(transactional=False) as repos:
        session = await repos.call_sessions.get(call_id)
        calls = await repos.call_sessions.list_by_patient(patient["patient_id"])
    assert session is not None and str(session.patient_id) == patient["patient_id"]
    assert session.status is CallStatus.COMPLETED
    assert session.summary == "Caller registered as a new patient."
    assert session.recording_url == f"https://storage.vapi.ai/{call_id}.wav"
    assert [c.call_id for c in calls] == [call_id]


async def test_a_dropped_call_is_abandoned_with_no_patient(
    client: httpx.AsyncClient, uow: UnitOfWork
) -> None:
    call_id = new_call_id()
    await tools(client, call_id, ("save_fields", {"fields": {"first_name": "Jane"}}))
    report = fixture("end_of_call_report", call_id)
    report["message"]["endedReason"] = "customer-ended-call"
    assert (await post(client, report)).status_code == 200
    async with uow(transactional=False) as repos:
        session = await repos.call_sessions.get(call_id)
    assert session is not None
    assert (session.status, session.patient_id) == (CallStatus.ABANDONED, None)
    assert session.draft == {"first_name": "Jane"}  # partial data is kept for review
    assert session.ended_reason == "customer-ended-call"


async def test_unknown_tool_and_bad_arguments_are_results_not_http_errors(client: httpx.AsyncClient) -> None:
    call_id = new_call_id()
    unknown, bad_args = await tools(
        client, call_id, ("delete_everything", {}), ("submit_registration", {"readback_version": "soon"})
    )
    assert unknown["error"] == "unknown_tool" and unknown["say"]
    assert bad_args["error"] == "invalid_arguments" and bad_args["say"]


async def test_tool_call_without_a_call_id_still_gets_a_result(client: httpx.AsyncClient) -> None:
    body = {
        "message": {
            "type": "tool-calls",
            "toolCallList": [{"id": "x", "name": "get_readback", "parameters": {}}],
        }
    }
    response = await post(client, body)
    assert response.status_code == 200
    assert json.loads(response.json()["results"][0]["result"])["error"] == "no_call_id"


async def test_stale_submit_and_start_over_through_the_webhook(client: httpx.AsyncClient) -> None:
    call_id = new_call_id()
    complete = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1980-03-05",
        "sex": "Female",
        "phone_number": unique_phone(),
        "address_line_1": "1 Main St",
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701",
    }
    await tools(client, call_id, ("save_fields", {"fields": complete}))
    (readback,) = await tools(client, call_id, ("get_readback", {}))
    await tools(client, call_id, ("save_fields", {"fields": {"city": "Dallas"}}))

    (stale,) = await tools(
        client, call_id, ("submit_registration", {"readback_version": readback["readback_version"]})
    )
    assert stale["status"] == "stale_readback"

    (again,) = await tools(client, call_id, ("get_readback", {}))
    assert len(again["chunks"]) == 1 and "Dallas" in again["chunks"][0]  # only the changed chunk

    (reset,) = await tools(client, call_id, ("reset_registration", {}))
    assert reset["cleared"] is True
    (after,) = await tools(client, call_id, ("get_readback", {}))
    assert after["ready"] is False and "first_name" in after["missing"]


async def test_caller_id_shortcut_through_the_webhook(client: httpx.AsyncClient) -> None:
    (result,) = await tools(client, new_call_id(), ("save_fields", {"fields": {"phone_number": "CALLER_ID"}}))
    assert result["saved"] == ["phone_number"] and result["errors"] == []
