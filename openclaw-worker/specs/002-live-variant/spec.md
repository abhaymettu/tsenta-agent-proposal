# Spec 002: ideal-agent live variant (isolated, simulation)

Status: draft, built as a variant of the scripted demo. The canonical repo and its 8521 server are not touched; the parent decides adoption.

## Goal

Typing in the phone thread reaches a fast Claude model that answers in iMessage style and may propose one narrowly typed intent. Deterministic code checks the intent against state and synthetic fixtures, applies it through the existing reducer (`core.js`), and only then changes the UI. Everything stays synthetic and labelled as a simulation.

## Non-goals

No real messages, mail, calendar, portal or account. No writes to Tsenta's or any real backend (the demo's own local SQLite file is the only store). No Tsenta integration. No production claim. No streaming of model text (see Decisions).

## Sources of truth, in order

1. Reducer state (`core.js`), built from scripted events and accepted intents.
2. Fixtures (`fixtures.js`): staged fictional evidence the code may cite (portal receipt checks) and the route options the code may propose. Claude cannot add to them.
3. The candidate's own words, recorded as `evidence: "Maya said so"` for link and manual-done intents only.

Claude's text is never a source. It cannot create receipts, employer confirmations, interview times, source health, recipients or routes.

## Provenance and absence rules (enforced before anything else)

- A healthy source means "connected; new mail from it reaches Tsenta". It does not mean its contents were read in this demo. The model never sees mailbox contents.
- Reply status comes from `Core.replyStatus` only: `replied`, `maybe_replied` (an interview request not linked to a role lists this application as a candidate), `waiting` (all mail sources healthy, no reply recorded), `unknown` (a mail source is down), or `receipt_*` (not a confirmed application). Never "rejected".
- Superseded 07:35: the regex reply guard was removed with model reply text. A regex cannot establish grounding; code-written replies remove the free text it was trying to police.
- When the model's intent is declined by code, the UI shows a code-written reply ("That didn't go through: <reason>") instead of the model's text, so a claimed action that did not happen is never shown.

## Intent contract

Revised 07:35 after the operator's groundedness block: Claude returns `{intent}` only and never writes the agent's message. `voice.js` writes every reply from state after the intent is checked (absence phrased as "on record", interrupted work as "may or may not have gone through"). Consequential intents (approve, link, manual_done, pause, resume, route_choose, route_undo) never apply on the model's reading of free text (revised ~08:10 after the Opus review showed keyword gates approving "I can't approve this"): code asks a question built from state, and only a short whole-message yes, answered by code with no model call, applies it after re-checking current state. Pause and resume also apply directly when the whole message is the bare command, and route undo when the message names the route ("undo the route"). The yes must answer the question in the agent's latest live message, captured when Maya sends; any later message or scripted step drops it. link first asks which role unless Maya's words (the employer name removed as a phrase, so "Lumen Data" names no role but "the data one" does) name exactly the proposed one; her answer to that question is read by code with no model call and still gets the yes question (revised 10:39, 0e8b841). Approval is built from `state.pending`, never from model fields. `intent.type` is `answer` (with a fixed topic) or one of the types below; unused fields are empty strings or 0. `intents.js` maps an intent to reducer events or declines it with a plain reason. Nothing else changes state.

| Intent | Accepted only when | Events |
|---|---|---|
| `answer` (topic, optional oppId) | topic is one of replies, receipts, interviews, open_items, sources, permissions, cannot, scope, unclear | none; voice.js answers from state |
| `pause` | not paused | `paused` |
| `resume` | paused | `resumed` (in-flight work becomes unknown-effect + a reconcile task, by the reducer) |
| `draft` (taskId, body) | not paused; task is an open reply task with an interview; no placed/retired action for it; body 1 to 700 chars | `draft` (recipient is the interview sender, set by code; action id A2, A3... by code) then `ask_approval` |
| `redraft` (actionId, body) | not paused; action exists and is drafted or approved, not placed or retired | `draft` (new version, same recipient) then `ask_approval` |
| `approve` | not paused; an open question exists (`state.pending`); built from it, model fields ignored; Maya says yes | `yes` (exact) then `placed` (Gmail draft; the candidate sends) |
| `reconcile` (oppId) | the application is unknown-effect AND a fixture holds evidence for it | `reconciled` with the fixture's found/source |
| `link` (interviewId, oppId) | interview unlinked; the role is the one candidate Maya's words name (the model's oppId is ignored; otherwise code asks which); Maya says yes to it | `link`, evidence "Maya said so" |
| `manual_done` (taskId) | an open reply task (T-reply-*); Maya says yes | `manual_done` (retires drafts, approvals and nudges in Tsenta's records) |
| `route_propose` (routeId) | routeId is a fixture option; not already the current route (replaces an open proposal; keeps undo history) | `route_propose` with the fixture's from/to/why |
| `route_choose` (routeId) | open proposal equals that fixture option | `route_choose` |
| `route_undo` | a previous route exists | `route_undo` |
| `show_status` (section) | section is `overview`, `applications` or `setup` | none; the reply is status text written by code from state |

The reducer keeps its own guards (stale versions, late revisions, epochs, duplicates). `ask_approval` records the epoch; `yes` with a recipient or epoch that differs from the open question is ignored.

## Status text (11:00 owner change: text templates, not an image)

`status.js` `statusText(state, section, clock)` writes short text from state (no model text), built once at reply time. Later state never changes a stored message. A blank line starts a new bubble. Sections:

- `overview`: three short messages: applied (confirmed, then other receipt states); replies (replied, invites to link, waiting, and unknown with the source that is down); what needs her. No bullets, header or footer (owner 15:59: "status 2-3 short lines").
- Presenter view (default): one disclosure line at the top of the thread ("Demo · synthetic people and jobs · nothing is sent"), short bubbles, the draft as a quoted message marked as written by Claude. Events, per-message tags, the state panel, scene list and the other cards are the debug view (S, or `?debug=1`).
- `applications` ("details"): one line per application: receipt and reply status.
- `setup`: goal, sources with status and since when, permission rules.

Zero is shown as 0; unknown is shown as unknown with its reason. They are never merged. The bubble keeps line breaks (`white-space: pre-line`).

iMessage capabilities considered (official sources, 2026-10-13): polls are user-created only, iOS 26+ and iMessage only (support.apple.com/guide/iphone/poll-people-in-a-conversation-iphde1787df4/ios), not something a bot can send; quick replies and list pickers exist only for Messages for Business through an approved provider (register.apple.com/resources/messages/msp-rest-api/type-interactive); text formatting needs iOS 18+ (support.apple.com/en-us/104970). So the demo sends plain text, and more detail is one more message away.

## Demo backend (11:00 owner unit)

Local, loopback only (127.0.0.1), no new secret. `server/serve.py` with stdlib `sqlite3`, file `server/demo.db` (`TSENTA_DB`):

- `events(seq, at, source 'seed'|'live', event)`: append-only, the durable source. Start-up replays it through `core.js` and refreshes the cached state.
- `messages(id, at, who 'me'|'them'|'sys', text, tag, card, card_state, key UNIQUE, response)`: the thread as shown; a card stores the state it was drawn from.
- `meta(k, v)`: cached state, the open question, the demo clock, when it was seeded.

Rules run in one long-lived node process (`server/worker.js`) that loads the same `turn.js`, `intents.js`, `core.js` and `voice.js` as the tests, so there is one rule set, not a port.

- `GET /api/thread`: state, messages, `seen` (agent messages so far), event count, seeded time.
- `POST /api/message {text, key, seen}`: one at a time (`TURN_LOCK`). A repeated key returns the stored response (a retry is answered once). If `seen` differs from the stored agent-message count, the open question is dropped: a yes typed before a newer agent message never answers the older question. Rules first; Claude only when they can't answer; then one transaction writes her message, the accepted events, the reply and a sys line. A failed model call stores an error reply, changes nothing and drops the question. Without Claude, code answers what it can and says Claude isn't connected.
- `POST /api/reset`: back to the seeded demo data (scenes 1 to 6 as events, no messages).
- Time budget, measured from the request's arrival: at most 15 s waiting for the turn lock (then 503, nothing stored); the call's phases (connect, write, pool, read) fit what is left of 22 s; the second rules call ends before the browser's 25 s abort. A server that trickles bytes inside the read timeout is not bounded further, and a second server on the same file is unsupported (a conflicting write gets 409, nothing stored).
- Only the page's own files are served (index.html, styles.css, app.js, core.js, scenes.js, matched exactly); server files, tests and .git are 404. POSTs take JSON from this page only.
- `seen` is `<epoch>:<agent-message count>`; each reset draws a new epoch, so a tab from before a reset can't answer a question asked after it.

The browser plays scenes 1 to 5 locally as before; at the end of scene 6 it loads the stored thread and renders it. `/api/agent` stays for `tests/live_eval.mjs` and stores nothing.

## Scene 6: "Your turn" (variant only)

Staged fictional events (code-authored, labelled) set up live work: a second Lumen Data role, an unlinked invite from Priya at Lumen Data, an interrupted Corvid Systems submit and a pause. Then the thread hands over to typing.

## Model choice

Live path uses Haiku 5.5 or Sonnet 5.5 (Opus is review only). Chosen by a bounded measurement. Since the 07:35 revision `tests/live_eval.mjs` goes through the running server and the browser's code path, and reports raw model results (intent type and fields, draft body) separately from delivered results (code-written text patterns and resulting state), including adversarial cases where the model may mislabel a message as consequential. These are pattern checks over a small fixed sample, not proof of grounding or a rate.

## Decisions

- No streaming: there is no model reply text to stream; the reply is written by code after the intent check. Latency is handled by model choice and short outputs.
- Fast paths (10:39, 0e8b841): a bare yes, a role named in answer to "which role?" and bare commands (pause, resume, "undo the route") are answered in the browser with no model call, checked against state like any proposal. The server reads the Keychain key once per process (memory only) and reuses one API client, so a request no longer pays a Keychain subprocess and a new TLS handshake.
- Delta review fixes (10:46, 68762b0; follow-up verification fixes in ff62925 10:52): any failed live reply drops the open question; negation or doubt in Maya's words never names a role, and her named role must agree with any candidate the model read; while a question is open only the plain words pause, resume and "undo the route" run locally (synonyms go to the model); the silence card's rows come from `Core.replyStatus`; the server's in-process lock is bounded so lock wait plus the call stays under the browser's 25 s abort.
- Scene 5 (variant): the scripted "No." to "am I just getting rejected everywhere?" and the card's "No rejection observed" became "Tsenta doesn't track rejections", matching live replies.
- Spend: one ledger shared with the earlier isolated server (`TSENTA_SPEND_FILE`). A $0.50 cap applied until 11:00 on 2026-10-13; the owner removed it then and the code no longer has one (owner: the key bills to the main account's promo credits; stop and report if credits run low or a card would be charged), priced from the official pricing page (fetched 2026-10-13): Haiku 5.5 $0.10/$0.50, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20 per MTok. The ledger is the server's own estimate from usage tokens, not a billing statement.

## Acceptance (deterministic, no browser)

- `node --test tests/`: reducer rules (existing 14), intent contract (each accept and decline path), `turn.js` (rules first, consent, which-role, draft, decline), status text (zero vs unknown, line length, snapshot independence), the thin browser client (key and `seen` fixed at send, stored rows rendered, unstored replies make `seen` -1, stale responses dropped) with a stubbed fetch.
- `python3 -m unittest discover tests`: schema, pricing, config, time budget, and the backend for real (temp SQLite file and the real node worker, model stubbed): restart rebuild, idempotent key, `seen` rule, failed call, no-Claude mode, reset, bad requests.
- Bounded live evidence: `tests/live_eval.mjs` results file with per-call latency, raw and delivered checks, and the ledger after the run.
