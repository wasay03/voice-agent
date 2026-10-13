# The voice agent: prompt and tool design

Everything Vapi needs is in this folder and is pushed by [`scripts/sync_assistant.py`](../scripts/sync_assistant.py), so the prompt, the voice settings and the tool schemas are versioned with the code.

| File | What it is |
|---|---|
| [`prompts/system_prompt.md`](prompts/system_prompt.md) | The system prompt. Lines starting with `//` explain why each section exists; they are stripped before the prompt is sent to Vapi. |
| [`prompts/first_message.md`](prompts/first_message.md) | The greeting, spoken before the model's first turn |
| [`assistant.yaml`](assistant.yaml) | Model, transcriber, voice, turn-taking, idle handling, tool messages, call summary |
| [`environments.yaml`](environments.yaml) | `ava-dev` (no phone number, for test calls) and `ava-prod` (attached to the number) |

Tool schemas are not written here. The sync script exports them from the tool classes in [`app/agent/tools/`](../app/agent/tools/), so the definitions the model sees cannot drift from the code that handles them.

## Design principles

**The model converses; the server decides.** The model's job is to understand speech, pick the next question and map what it heard to canonical values (a spoken date to `YYYY-MM-DD`, spelled letters to a word). Everything that must be correct is the server's: validation, what has been collected, what is still missing, the confirmation wording, and whether a save happened.

**The prompt describes behaviour, not facts.** It never asks the model to remember the caller's answers. `save_fields` returns `next_missing`, and the model is told to use that, and never to say something is saved unless a tool said so.

**Voice style comes first in the prompt.** One or two short sentences per turn, one question at a time, varied acknowledgements, no symbols or abbreviations, no repeating each answer back. Most "robotic" agents fail on these, not on logic.

**Every tool result says what to do or say next.** A rejected field comes back with a spoken re-ask written for that error (`"I only got nine digits. Could you say the whole number again, including the area code?"`). Flow results carry a `next` instruction (`"When the caller says yes, call get_readback with part='address_extras'."`). The model does not have to infer the protocol.

**Where the model must not improvise, it does not speak.** A tool result can carry text that Vapi speaks verbatim in place of a model reply (the `request-complete` message of the tool result). The confirmation readback, the closing line and the final failure apology use it.

## What live calls changed

The first version followed the design document: the model was given the readback text and told to read it exactly. Two test calls on `ava-dev` showed where that was not enough. Each finding below came from the call's log (what the model said, each tool call, each result).

| Observed on a live call | Change |
|---|---|
| The model read only "I have your name as Jane Test" from a part that also held the date of birth, sex and phone number, then asked "Is that all correct?". The caller confirmed details they never heard, and the record was saved. | The readback is spoken by Vapi from the server's text, one part at a time. The model is told to say nothing in that turn. |
| "One moment", "Just a sec", "Give me a moment" before almost every turn | These are Vapi's default fillers when a tool has no start message. An empty start message silences them; a delayed message covers genuinely slow calls. Tools answer in about a second. |
| After the save, the agent offered to have the front desk call back, which nothing can do. The call summary then told staff to follow up. | The prompt forbids offering anything the tools cannot do. |
| The call ended with "Goodbye" and no "You're all set, [First Name]" | The closing line is returned by `submit_registration` and spoken by Vapi, which then hangs up. |
| After a correction during the first part, the server listed only that part for re-reading. The address part was read only because the model remembered it existed. | Each part carries a `delivered` flag. A part never read stays pending, and `submit_registration` returns `readback_incomplete` until every part has been read. |
| The model read the address in its own words, the caller said yes, then the tool read the real text and the model saved without a second yes. | The prompt forbids the model from stating details during confirmation, and results carry an explicit `next` step. This one is only prompt-enforced: the server can prove a part was read, not that the caller answered. |
| Vapi rejected a tool whose optional argument had an `anyOf` schema | Optional arguments are flattened to a plain type on export; a test checks every tool schema. |

Two things the model still does against the prompt, left alone because they are harmless: it asks for the street address on its own instead of the whole address in one question, and it lists the four options when asking for sex.

## Voice settings worth knowing

- **Transcriber:** Deepgram Nova-3 with `numerals` on, so spoken digits arrive as digits, and insurer names as key terms.
- **Barge-in:** the agent stops after two words from the caller. Backchannel words ("okay", "yeah") do not interrupt.
- **Endpointing:** smart endpointing, so a pause in the middle of a phone number is not taken as the end of the turn.
- **Idle callers:** `customer.speech.timeout` hooks: "Are you still there?" after 8 seconds, then a goodbye and hang-up.
- **Limits:** calls are capped at 10 minutes. Only the four webhook events the service handles are sent.
- **Webhook auth:** a shared secret in the `X-Vapi-Secret` header, set through `server.headers`.

## Changing the agent

```bash
make sync-dev                                          # push to ava-dev, then test from the Vapi dashboard
uv run python scripts/sync_assistant.py --env prod --diff   # see what would change in production
make sync-prod                                         # diff, confirm, push, re-attach the number
```

If a change needs new tool behaviour, deploy the server first. The prompt and the tools are a pair.
