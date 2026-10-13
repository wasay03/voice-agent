# Voice Patient Registration Agent

A voice AI agent, reachable on a real US phone number, that registers new patients through natural
conversation, saves them to PostgreSQL, and exposes the records through a REST API.

> **Status: under construction.** The full README (live number, API URL, architecture, trade-offs)
> lands with the first end-to-end call. Design docs are in [`docs/`](docs/).

## Stack

Vapi (telephony, Deepgram speech-to-text and text-to-speech, LLM loop) → FastAPI service → Neon PostgreSQL 18.
Every database read goes through a SQL function (`sql/functions/`) and every write through a stored
procedure (`sql/procedures/`); see [`sql/migrations/README.md`](sql/migrations/README.md).

## Quick start

```bash
cp .env.example .env            # fill in DATABASE_URL and API_KEY at minimum
uv venv venv && make install    # dependencies into ./venv
make db-up                      # local Postgres 18 (or point DATABASE_URL at Neon)
make migrate                    # apply sql/
make dev                        # http://localhost:8000/docs
make test                       # needs Docker (starts a throwaway Postgres)
```
