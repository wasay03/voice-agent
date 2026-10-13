"""Webhook authentication: a shared secret Vapi sends on every request.

The assistant's `server.headers` carries `X-Vapi-Secret: <VAPI_WEBHOOK_SECRET>`; a Vapi
credential configured as a Bearer token is accepted too (`Authorization: Bearer <secret>`).
"""

from fastapi import Header

from app.api.deps import ContainerDep
from app.core.errors import AuthenticationError
from app.core.security import secret_matches


def verify_webhook(
    container: ContainerDep,
    x_vapi_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    expected = container.settings.vapi_webhook_secret
    bearer = authorization.removeprefix("Bearer ").strip() if authorization else None
    if secret_matches(x_vapi_secret, expected) or secret_matches(bearer, expected):
        return
    raise AuthenticationError("Missing or invalid webhook secret.")
