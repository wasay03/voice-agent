import asyncpg
import pytest

from app.db.migrator import migrate


async def test_second_run_is_a_no_op(database_url: str) -> None:
    report = await migrate(database_url)  # the session fixture already ran it once
    assert not report.baseline_applied
    assert report.versioned == []
    assert report.repeatable == []


async def test_baseline_creates_tables_and_seeds(database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        tables = {
            r["table_name"]
            for r in await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        }
        assert {"patients", "call_sessions", "us_states", "schema_migrations"} <= tables
        assert await conn.fetchval("SELECT count(*) FROM us_states") == 56
        assert await conn.fetchval("SELECT count(*) FROM patients WHERE last_name = 'Doe'") >= 1
    finally:
        await conn.close()


async def test_future_date_of_birth_is_rejected_by_the_trigger(database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        with pytest.raises(asyncpg.CheckViolationError) as info:
            await conn.execute(
                """
                INSERT INTO patients (first_name, last_name, date_of_birth, sex, phone_number,
                                      address_line_1, city, state, zip_code)
                VALUES ('Future', 'Person', CURRENT_DATE + 1, 'Other', '5125550100',
                        '1 Main St', 'Austin', 'TX', '78701')
                """
            )
        assert info.value.constraint_name == "patients_date_of_birth_not_future"
    finally:
        await conn.close()


async def test_names_accept_unicode_letters(database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        pattern = "^[[:alpha:]]+([ '-][[:alpha:]]+)*$"
        for name in ("José", "O'Brien-Smith", "De La Cruz"):
            assert await conn.fetchval("SELECT $1 ~ $2", name, pattern), name
    finally:
        await conn.close()
