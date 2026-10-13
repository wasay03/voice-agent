import httpx


async def test_healthz_does_not_need_the_database(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}, "error": None}


async def test_health_reports_database_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok", "db": "ok"}
    assert response.headers["X-Request-ID"]


async def test_unknown_route_uses_the_envelope(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    body = response.json()
    assert response.status_code == 404
    assert body["data"] is None
    assert body["error"]["code"] == "not_found"
