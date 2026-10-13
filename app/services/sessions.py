"""Shared by the services that operate on a call: get the call's session, creating it if needed."""

from app.db.unit_of_work import Repositories
from app.domain.entities import CallSession


async def ensure_session(repos: Repositories, call_id: str, caller_number: str | None = None) -> CallSession:
    """Lock and return the session for `call_id`.

    A tool call can arrive before the call-start webhook, and the caller's number may only be
    known from one of them; both paths therefore create the row idempotently and fill in a
    missing caller number.
    """
    session = await repos.call_sessions.lock(call_id)
    if session is None or (session.caller_number is None and caller_number):
        await repos.call_sessions.start(call_id, caller_number)
        session = await repos.call_sessions.lock(call_id)
    if session is None:  # the row was just inserted; losing it would be a database fault
        raise RuntimeError(f"call session {call_id} could not be created")
    return session
