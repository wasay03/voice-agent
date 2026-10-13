"""Constant-time secret comparison shared by the REST API and the Vapi webhook."""

import hmac

from pydantic import SecretStr


def secret_matches(provided: str | None, expected: SecretStr) -> bool:
    if not provided:
        return False
    return hmac.compare_digest(provided.encode(), expected.get_secret_value().encode())
