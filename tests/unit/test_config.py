import pytest

from app.core.config import normalize_dsn


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (
            "postgresql://u:p@h/db?sslmode=require&channel_binding=require",
            "postgresql://u:p@h/db?sslmode=require",
        ),
        ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"),
        ("postgresql+asyncpg://u:p@h/db?sslmode=require", "postgresql://u:p@h/db?sslmode=require"),
    ],
)
def test_normalize_dsn(given: str, expected: str) -> None:
    assert normalize_dsn(given) == expected
