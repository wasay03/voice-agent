"""The REST API end to end: routing, auth, envelope, status codes, headers."""

from uuid import uuid4

import httpx
import pytest

from tests.conftest import TEST_API_KEY, patient_payload, unique_phone

AUTH = {"X-API-Key": TEST_API_KEY}


async def create(client: httpx.AsyncClient, **overrides: object) -> dict:
    response = await client.post("/patients", json=patient_payload(**overrides), headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_requires_api_key(client: httpx.AsyncClient) -> None:
    for headers in ({}, {"X-API-Key": "wrong"}):
        response = await client.get("/patients", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


async def test_create_returns_201_location_and_normalised_record(client: httpx.AsyncClient) -> None:
    body = patient_payload(
        first_name="jane", state="texas", phone_number="+1 (512) 555-0123", date_of_birth="1980-03-05"
    )
    response = await client.post("/patients", json=body, headers=AUTH)
    assert response.status_code == 201
    payload = response.json()
    assert payload["error"] is None
    patient = payload["data"]
    assert response.headers["Location"].endswith(f"/patients/{patient['patient_id']}")
    assert (patient["first_name"], patient["state"], patient["phone_number"]) == ("Jane", "TX", "5125550123")
    assert patient["date_of_birth"] == "03/05/1980"
    assert patient["deleted_at"] is None


async def test_create_field_errors_are_422_with_details(client: httpx.AsyncClient) -> None:
    body = patient_payload(phone_number="555", date_of_birth="2999-01-01")
    response = await client.post("/patients", json=body, headers=AUTH)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {(d["field"], d["code"]) for d in error["details"]} == {
        ("phone_number", "phone_length"),
        ("date_of_birth", "dob_future"),
    }


async def test_create_rejects_server_owned_fields(client: httpx.AsyncClient) -> None:
    response = await client.post("/patients", json=patient_payload(patient_id=str(uuid4())), headers=AUTH)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["code"] == "extra_forbidden"


@pytest.mark.parametrize("content", [b"{not json", b""])
async def test_unreadable_body_is_400(client: httpx.AsyncClient, content: bytes) -> None:
    response = await client.post(
        "/patients", content=content, headers={**AUTH, "Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


async def test_get_by_id(client: httpx.AsyncClient) -> None:
    created = await create(client)
    response = await client.get(f"/patients/{created['patient_id']}", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["data"] == created


async def test_get_malformed_id_is_400_missing_is_404(client: httpx.AsyncClient) -> None:
    assert (await client.get("/patients/not-a-uuid", headers=AUTH)).status_code == 400
    response = await client.get(f"/patients/{uuid4()}", headers=AUTH)
    assert response.status_code == 404
    assert response.json() == {
        "data": None,
        "error": {
            "code": "not_found",
            "message": response.json()["error"]["message"],
            "details": [],
            "request_id": response.headers["X-Request-ID"],
        },
    }


async def test_list_filters_and_total_header(client: httpx.AsyncClient) -> None:
    phone = unique_phone()
    for first in ("Amy", "Ben"):
        await create(
            client, first_name=first, last_name="Filterable", phone_number=phone, date_of_birth="1990-01-02"
        )

    response = await client.get("/patients", params={"last_name": "filterable"}, headers=AUTH)
    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "2"
    assert {p["first_name"] for p in response.json()["data"]} == {"Amy", "Ben"}

    formatted = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
    response = await client.get(
        "/patients", params={"phone_number": formatted, "date_of_birth": "01/02/1990"}, headers=AUTH
    )
    assert response.headers["X-Total-Count"] == "2"

    response = await client.get("/patients", params={"last_name": "filterable", "limit": 1}, headers=AUTH)
    assert len(response.json()["data"]) == 1 and response.headers["X-Total-Count"] == "2"


@pytest.mark.parametrize(
    "params",
    [{"date_of_birth": "31/31/1990"}, {"limit": 0}, {"limit": 500}, {"phone_number": "123"}, {"foo": "x"}],
)
async def test_list_bad_query_is_400(client: httpx.AsyncClient, params: dict) -> None:
    response = await client.get("/patients", params=params, headers=AUTH)
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "bad_request"


async def test_partial_update(client: httpx.AsyncClient) -> None:
    created = await create(client, email="old@example.com")
    response = await client.put(
        f"/patients/{created['patient_id']}", json={"city": "dallas", "email": None}, headers=AUTH
    )
    assert response.status_code == 200
    updated = response.json()["data"]
    assert (updated["city"], updated["email"], updated["first_name"]) == (
        "Dallas",
        None,
        created["first_name"],
    )
    assert updated["updated_at"] > created["updated_at"]


async def test_update_errors(client: httpx.AsyncClient) -> None:
    created = await create(client)
    url = f"/patients/{created['patient_id']}"
    assert (await client.put(url, json={"last_name": None}, headers=AUTH)).status_code == 422
    assert (await client.put(url, json={"zip_code": "1"}, headers=AUTH)).status_code == 422
    assert (await client.put(url, json={}, headers=AUTH)).status_code == 422
    assert (await client.put(f"/patients/{uuid4()}", json={"city": "Waco"}, headers=AUTH)).status_code == 404


async def test_soft_delete(client: httpx.AsyncClient) -> None:
    created = await create(client, last_name="Deletable")
    url = f"/patients/{created['patient_id']}"
    response = await client.delete(url, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["data"]["deleted_at"] is not None
    assert (await client.get(url, headers=AUTH)).status_code == 404
    assert (await client.delete(url, headers=AUTH)).status_code == 404
    listed = await client.get("/patients", params={"last_name": "Deletable"}, headers=AUTH)
    assert created["patient_id"] not in {p["patient_id"] for p in listed.json()["data"]}


async def test_seed_patient_is_available(client: httpx.AsyncClient) -> None:
    response = await client.get("/patients/01920000-0000-7000-8000-000000000001", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["data"]["last_name"] == "Doe"
