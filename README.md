# Voice Patient Registration Agent

A voice AI agent on a real US phone number that registers new patients through natural conversation, saves them to PostgreSQL, and exposes the records through a REST API.

| | |
|---|---|
| **Call it** | **+1 (682) 341-4217** |
| **API** | https://voice-agent-production-ec4c.up.railway.app |
| **API docs** | https://voice-agent-production-ec4c.up.railway.app/docs |
| **Auth** | `X-API-Key` header. The key is in the submission notes, not in this repo. |

```bash
export API=https://voice-agent-production-ec4c.up.railway.app
export KEY=<api key from the submission notes>

curl -H "X-API-Key: $KEY" "$API/patients"                              # everyone registered so far
curl -H "X-API-Key: $KEY" "$API/patients?last_name=doe"                # filters: last_name, date_of_birth, phone_number
curl -H "X-API-Key: $KEY" "$API/patients/<patient_id>/calls"           # transcript of the call
```

Call the number, register, hang up, then run the first `curl`: the record is there. Call again and give the same phone number: the agent recognises you and offers to update your record.

## How it works

```
Caller ──phone──► Vapi ─────────────────────────────► FastAPI service (Railway) ───► PostgreSQL 18 (Neon)
                  number, speech-to-text (Deepgram),    POST /webhooks/vapi  tool calls, call events
                  text-to-speech (Deepgram Aura),       /patients            REST API
                  turn-taking, LLM loop (GPT-4.1)
```

The LLM never holds the truth about what is being saved. It calls tools; each tool updates a **draft** stored in the call's database row. Four rules follow from that:

1. **One validation layer.** The REST API and the voice tools run the same validator per field ([app/domain/validators.py](app/domain/validators.py)). The database repeats the critical rules as constraints.
2. **Server-side conversation state.** Out-of-order answers, corrections and "start over" are plain updates to the draft. A server restart mid-call loses nothing.
3. **What the caller confirms is what gets saved.** The confirmation text is written by the server from the draft and spoken by Vapi word for word, not by the model. Saving is refused if the draft changed after it was read, or if any part of it has not been read aloud yet.
4. **No silence, no false claims.** Every failure is a tool result with a line to say. The closing "You're all set, [First Name]" is spoken by the platform only after the database write succeeded.

### Layers

```
api/ (REST)                    telephony/vapi/ (webhook: the only Vapi-specific code)
     │                                   │
     │                              agent/ (tools, spoken wording)
     └────────────► services/ ◄──────────┘     business logic only: no SQL, no connections
                        │
                 db/unit_of_work.py             one transaction; hands out repositories
                        │
                 db/repositories/               one routine call per method
                        │
                 db/client.py                   pool, transactions, error translation
                        │
                 PostgreSQL                     sql/functions/ (reads)   sql/procedures/ (writes)
```

Every database read is a SQL function and every write a stored procedure, one per file under [sql/](sql/). Tables are one file each in [sql/models/](sql/models/); all indexes are in [sql/indexes.sql](sql/indexes.sql). [tests/unit/test_architecture.py](tests/unit/test_architecture.py) fails the build if a repository touches a table directly or a service imports the database driver.

| Path | What lives there |
|---|---|
| [app/domain/](app/domain/) | Field rules, Pydantic models, US states. No I/O. |
| [app/services/](app/services/) | `PatientService`, `RegistrationService` (draft, readback, submit), `CallLogService` |
| [app/agent/tools/](app/agent/tools/) | The five tools the model can call, one per file |
| [app/agent/speech/](app/agent/speech/) | Server-written spoken text: readback, re-prompts, formatters ("March 5th, 1980") |
| [app/telephony/vapi/](app/telephony/vapi/) | Webhook auth, payload parsing, dispatch |
| [app/db/](app/db/) | Client, unit of work, repositories, migrator |
| [sql/](sql/) | Types, tables, indexes, triggers, functions, procedures, seed data |
| [assistant/](assistant/) | The prompt and voice settings, pushed to Vapi by [scripts/sync_assistant.py](scripts/sync_assistant.py) |

## The voice agent

The system prompt is [assistant/prompts/system_prompt.md](assistant/prompts/system_prompt.md), with a comment above each section explaining why it is there. The design reasoning, including what two rounds of live test calls changed, is in **[assistant/README.md](assistant/README.md)**.

| Tool | When the model calls it | What the server does |
|---|---|---|
| `save_fields` | The caller gives or corrects anything, in any order | Validates each field on its own, merges the good ones into the draft, returns what is still missing and a spoken re-ask for each bad field. Looks up existing patients when a phone number is saved. |
| `get_readback` | All required fields are in | Renders the confirmation text; Vapi speaks it verbatim, one part at a time |
| `submit_registration` | The caller said yes to every part | Checks the version and that every part was read, writes the patient once, speaks the closing line and ends the call |
| `switch_to_update` | A returning caller wants to update their record | Loads the existing record into the draft (only for a patient matching the phone number given) |
| `reset_registration` | The caller wants to start over | Clears the draft |

The call id and the caller's number come from Vapi's webhook, never from the model's arguments, so the model cannot touch another caller's session.

### What happens when things go wrong

| Situation | Behaviour |
|---|---|
| Invalid value (future date of birth, 9-digit phone) | A re-ask for that field only ("I only got nine digits…"); other answers from the same sentence are kept |
| Correction, at any point including the readback | The draft changes, the old readback is void, and only the changed part is read again |
| Caller hangs up mid-call | No patient row. The session is kept as `abandoned` with the partial draft and transcript. |
| Database write fails | "I'm having trouble saving that" and one retry; then an apology and the call ends. The session is `failed`, the payload is in the error log. The caller is never told it was saved. |
| The model retries a save, or the webhook is redelivered | `already_saved`: same patient, no second row (the call id is the idempotency key) |
| The model sends several tool calls at once | Applied in order under a row lock; none is lost |
| Caller is silent | A nudge after 8 seconds, then a goodbye and hang-up |
| "Can we start over?" | One confirmation, then the draft is cleared |
| Returning caller (same phone number) | "It looks like we already have a record for Jane Doe. Would you like to update your information instead?" |

## REST API

Every response uses the envelope `{ "data": ..., "error": null }` or `{ "data": null, "error": { "code", "message", "details": [{field, code, message}], "request_id" } }`.

| Method | Path | Notes |
|---|---|---|
| GET | `/patients` | Filters `last_name` (case-insensitive), `date_of_birth` (`MM/DD/YYYY` or `YYYY-MM-DD`), `phone_number` (any formatting); `limit` (1–200), `offset`; total in `X-Total-Count` |
| GET | `/patients/{id}` | 404 if missing or soft-deleted |
| POST | `/patients` | 201 with a `Location` header. Unknown fields are rejected. |
| PUT | `/patients/{id}` | Partial: only fields in the body change. Required fields cannot be nulled. |
| DELETE | `/patients/{id}` | Soft delete (`deleted_at`); the record disappears from every read |
| GET | `/patients/{id}/calls` | Calls linked to the patient: status, summary, transcript, recording URL |
| GET | `/health`, `/healthz` | Readiness (pings the database) and liveness |

Status codes: **400** unreadable (bad JSON, no body, malformed id, bad query parameter) · **401** missing or wrong API key · **404** not found · **422** a field breaks a rule, with one entry per field (`dob_future`, `phone_length`, `zip_invalid`, …) · **500** unexpected, with the request id only.

Input is normalised the same way on both paths: `"texas"` → `TX`, `"+1 (512) 555-0198"` → `5125550198`, `"o'brien"` → `O'Brien`. Dates of birth are returned as `MM/DD/YYYY`.

## Run it locally

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env            # set DATABASE_URL, API_KEY, VAPI_WEBHOOK_SECRET
uv venv venv && make install    # dependencies into ./venv
make db-up                      # Postgres 18 on localhost:5432
# for the local database: DATABASE_URL=postgresql://intake:intake@localhost:5432/intake
make migrate                    # applies sql/ (safe to run repeatedly)
make dev                        # http://localhost:8000/docs
make smoke                      # create/read/filter/update/delete against the running server
make test                       # 193 tests; starts a throwaway Postgres 18 in Docker
```

To take calls on a local server, expose it with a tunnel (`ngrok http 8000`), set `PUBLIC_BASE_URL` to the tunnel URL, and run `make sync-dev`. That creates or updates a separate `ava-dev` assistant, which you can talk to from the Vapi dashboard without touching the production number.

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string (Neon's `channel_binding` parameter is stripped automatically) |
| `API_KEY` | yes | Expected in the `X-API-Key` header |
| `VAPI_WEBHOOK_SECRET` | yes | Shared secret Vapi sends as `X-Vapi-Secret` on every webhook |
| `ENV` | no | `dev` (readable logs) or `prod` (JSON logs) |
| `CLINIC_TZ` | no | Time zone for "today" in date-of-birth checks. Default `America/New_York`. |
| `CLINIC_NAME`, `AGENT_NAME` | no | Substituted into the prompt by the sync script |
| `TOOL_TIMEOUT_SECONDS` | no | Deadline for the save step. Default 4. |
| `DB_POOL_MIN`, `DB_POOL_MAX`, `DB_STATEMENT_TIMEOUT_MS` | no | Connection pool settings |
| `PUBLIC_BASE_URL`, `VAPI_API_KEY`, `VAPI_PHONE_NUMBER_ID` | sync script only | Where Vapi should send webhooks, and the keys to configure the assistant. The running service never reads the last two. |

Speech-to-text, text-to-speech and LLM keys live in the Vapi account, so this service never sees them.

### Deployment

Railway builds the [Dockerfile](Dockerfile) on every push to `main`. The container runs the migrator, then uvicorn; if a migration fails, the health check never passes and the previous deployment keeps serving. `make sync-prod` shows a diff of the assistant, asks for confirmation, updates `ava-prod` and points the phone number at it.

## Tech stack and why

| Layer | Choice | Why |
|---|---|---|
| Telephony and voice | Vapi, with a Vapi-provided US number | Number, speech, turn-taking, barge-in and tool calling in one place, configured as code. Effort goes into the conversation and correctness instead of audio plumbing. |
| Speech | Deepgram Nova-3 (in) and Aura-2 (out) | Low latency; numerals mode turns "five one two" into digits |
| LLM | GPT-4.1 through Vapi | Reliable tool calling at phone-call latency |
| Backend | Python 3.13, FastAPI, Pydantic v2 | One set of models validates API bodies and tool arguments; OpenAPI docs for free |
| Database | PostgreSQL 18 on Neon | Enum types, CHECK constraints, partial indexes, `uuidv7()` ids, JSONB for the draft |
| Data access | asyncpg, SQL functions and procedures, no ORM | Every query is a named, versioned routine; the app holds no SQL of its own |
| Migrations | A small runner ([app/db/migrator.py](app/db/migrator.py)) | Tables once, versioned changes once each, routines re-applied when their file changes, all in one transaction |
| Hosting | Railway | Always-on container, so a tool call never waits on a cold start |
| Tests | pytest against a real Postgres 18 (testcontainers) | Constraints, triggers and routines are tested, not mocked |

## Testing

193 tests, run in CI on every push: field rules and spoken formatting (unit); every SQL routine and constraint through the repositories; the registration flow (out-of-order answers, corrections, stale and incomplete readbacks, double submit, concurrent tool calls, database failure and recovery, returning callers); all REST endpoints and status codes; and whole conversations replayed through the webhook over HTTP.

The agent itself was tested with live calls. The log of each call (what the model said, each tool call and result) drove the changes described in [assistant/README.md](assistant/README.md).

## Trade-offs and known limitations

- **Speech-to-text on names and emails is the weakest link.** The agent spells them back and corrections are cheap, but an unusual name can take a few turns.
- **The server guarantees every detail was read aloud, not that the caller answered.** Waiting for "yes" before saving still depends on the model following the prompt.
- **English only.** A Spanish speaker is told politely that the line is English-only. Multilingual transcription and a Spanish readback are designed but not built.
- **One registration per call.** After a save, the call ends; registering a second person needs a second call.
- **Caller ID is not identity.** A returning caller is matched by the phone number they give, and only the name on the record is spoken before they confirm. That is fine for a demo and not for production.
- **Phone numbers must be US (NANP) numbers**, as the brief specifies. An international number is re-asked for.
- **Addresses are not verified** against USPS or a geocoder.
- **Names accept letters from any alphabet, hyphens, apostrophes and single internal spaces** ("De La Cruz"), slightly wider than the brief's "alphabetic + hyphens/apostrophes".
- **Phone numbers are not unique**, because families share a phone. Duplicate detection is an offer the caller accepts, not a constraint.
- **Not HIPAA-ready.** Fake data only. Production would need agreements with every vendor, PHI-free logs, encryption at rest, an audit trail and a retention policy.
- **Free-tier hosting.** Railway's trial credit runs out about 30 days after sign-up; Neon suspends when idle and takes under a second to wake (the call-start webhook wakes it before the first tool call).

## Next steps

1. An automated conversation eval: scripted caller personas (played by an LLM) against the same prompt and tools, scored on whether the saved record matches the persona.
2. Spanish: multilingual transcription, a bilingual voice, and a Spanish readback template.
3. Appointment scheduling after registration (the tables are already in the schema).
4. A small dashboard listing patients with their call transcripts.
5. Resume after a dropped call: offer to pick up the abandoned draft when the same number calls back.
6. Address verification and ZIP-to-city confirmation.
7. A database role for the service that can only execute the routines, with no table privileges.
