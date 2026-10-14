# Agent endpoint contract (localhost only)

The browser never holds an API key. It talks to `server/serve.py` on `http://127.0.0.1:8521`, which owns the Claude call. Deterministic state lives in the browser's `core.js`; the server is stateless.

## GET /api/status

```json
{ "mode": "mock" | "live", "model": "claude-...", "spentUsd": 0.12, "reason": "why mock, if mock" }
```

`mode` is `live` only when a key was found in Keychain and `server/live.json` records a verified balance (no money cap since 2026-10-13; spend is recorded as an estimate). Anything else is `mock`, and the UI says so.

## POST /api/agent

Request:

```json
{
  "userText": "free text the presenter typed",
  "scene": 3,
  "state": { "...": "core.snapshot(state): synthetic fixture state only" },
  "pending": { "actionId": "A2", "version": 2, "recipient": "jordan@halyard.example" } | null
}
```

Response 200:

```json
{
  "mode": "live",
  "reply": "text for the agent bubble",
  "intent": null | { "type": "approve", "actionId": "A2", "version": 2 }
                | { "type": "pause" } | { "type": "resume" }
                | { "type": "route_choose", "to": "..." } | { "type": "route_undo" },
  "model": "claude-...",
  "usage": { "input_tokens": 0, "output_tokens": 0 },
  "spentUsd": 0.0
}
```

When live mode is off, the server answers 200 with `{"mode": "mock", "reason": ..., "reply": "<scripted reply from MOCK>", "intent": null}`.

Errors: `502 {"error":...}` on an upstream failure or an unreadable request body. On any non-200 the UI falls back to the scripted reply and shows a mock label.

## Rule: the model proposes, code decides

`intent` is a proposal. The browser passes it to `core.apply()` as an event, and the reducer accepts or ignores it by the same rules as scripted events. For example, an `approve` whose `actionId` or `version` does not match `state.pending` is ignored and logged. The model's `reply` text never changes state by itself.

## Ownership boundaries

- Root files (`index.html`, `styles.css`, `app.js`, `core.js`, `scenes.js`) and `tests/`: UI, state core, scenes.
- `server/`: static serving, the Claude proxy, Keychain lookup, spend estimate.
- `intercept/`: own-session client-side reroute of tsenta.com's chat to this endpoint. Read-only toward Tsenta.
