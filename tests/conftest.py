"""Shared fixtures: one real Postgres 18 per test session, migrated with the real migrator.

Set TEST_DATABASE_URL to reuse an existing database (e.g. `make db-up`) instead of starting
a container. Never point it at production: tests write data.
"""

import asyncio
import itertools
import os
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from testcontainers.community.postgres import PostgresContainer

from app.core.config import Settings
from app.db.client import DatabaseClient
from app.db.migrator import migrate
from app.db.unit_of_work import UnitOfWork
from app.main import create_app

TEST_API_KEY = "test-api-key"
TEST_WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    if url := os.environ.get("TEST_DATABASE_URL"):
        asyncio.run(migrate(url))
        yield url
        return
    with PostgresContainer("postgres:18", driver=None) as pg:
        url = pg.get_connection_url()
        asyncio.run(migrate(url))
        yield url


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        env="test",
        log_level="WARNING",
        database_url=database_url,
        api_key=TEST_API_KEY,  # type: ignore[arg-type]
        vapi_webhook_secret=TEST_WEBHOOK_SECRET,  # type: ignore[arg-type]
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http,
    ):
        yield http


@pytest.fixture
async def db(database_url: str) -> AsyncIterator[DatabaseClient]:
    client = DatabaseClient(database_url)
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def uow(db: DatabaseClient) -> UnitOfWork:
    return UnitOfWork(db)


_phone_counter = itertools.count(1000)


def unique_phone() -> str:
    """A valid, unused NANP number per call so tests never collide on duplicate detection."""
    return f"512555{next(_phone_counter):04d}"


def patient_payload(**overrides: object) -> dict[str, object]:
    return {
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": "1985-07-04",
        "sex": "Female",
        "phone_number": unique_phone(),
        "address_line_1": "1 Main St",
        "city": "Austin",
        "state": "TX",
        "zip_code": "78701",
        **overrides,
    }
