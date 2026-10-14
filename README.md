# Tsenta agent proposal: pitch and prototypes

Tsenta already applies to jobs for its users, and people can reach it from inside their AI assistant through its MCP server. This repo proposes the next step: one Tsenta core that holds the user's goal, a record of every application and message, and an exact yes for each consequential action. Any agent, the user's own or Tsenta's, can then work the job search proactively without guessing, inventing facts, or acting on a stale approval. The repo has the pitch deck and three working prototypes, all on fictional data. It is a proposed direction for discussion, not something Tsenta has adopted.

## What is here

| Folder | What it is | Runs on |
|---|---|---|
| `pitch/` | The pitch deck (29 slides, editable PPTX with speaker notes) and the Python source that builds it | python-pptx |
| `scripted-demo/` | A web page that looks like an iMessage thread with a Tsenta agent and plays five scripted scenes | Python 3 standard library, any browser |
| `live-chat-demo/` | The scripted demo plus a sixth scene where you type freely; Claude proposes, code decides | Python 3, Node, optional Anthropic API key |
| `openclaw-worker/` | A prototype job core driven by a real outside agent (OpenClaw) in an isolated container, with a sandbox ATS and mailbox | Python 3, Node, Docker, Anthropic API key for live turns |

Each folder is self-contained. Nothing is shared between them.

## Quickstart

### pitch

Open `pitch/Tsenta-Pitch.pptx`. To rebuild it from source:

```sh
cd pitch
uv run --no-project --with python-pptx python build/build_deck.py   # writes outputs/Tsenta-Pitch-2026-10-14.pptx
```

Slide text lives in `build/content.py` and the speaker notes in `build/notes.py`; `build/build_deck.py` is layout only.

### scripted-demo

```sh
cd scripted-demo
python3 server/serve.py              # http://127.0.0.1:8521/
node --test tests/*.test.js && python3 -m unittest discover tests
```

Space, Enter or the right arrow advances; 1 to 5 jump to a scene; S shows the agent-state panel. No network and no key are needed. A live mode exists but stays off unless an Anthropic key is set up (see the folder's README).

### live-chat-demo

```sh
cd live-chat-demo
PORT=8526 python3 server/serve.py    # then open http://127.0.0.1:8526/?scene=6&step=all
node --test tests/*.test.js && python3 -m unittest discover tests
```

Without a key, code still answers what it can and says Claude is not connected. For live replies, store a key in the macOS Keychain under the service `tsenta-prototype-anthropic`, add `server/live.json` as described in the folder's README, and start the server with `uv run --with anthropic python server/serve.py`. Live replies are paid API calls.

### openclaw-worker

```sh
cd openclaw-worker
python3 -m core.sandbox --port 8551 --db run/sandbox.db    # local ATS and mailbox sink
PORT=8550 python3 -m server.serve                          # http://127.0.0.1:8550/
python3 -m unittest discover tests && node --test openclaw/edge.test.mjs
```

Without the worker container, the core reports the worker as offline and nothing reaches a model. The worker itself is built from `openclaw/Dockerfile.worker` and `openclaw/Dockerfile.edge` on a pinned OpenClaw 2026.10.3 tarball, which is not included: download `openclaw-2026.10.3.tgz` from npm and point `OPENCLAW_TGZ` at it (`openclaw/phase1.sh` checks its sha256); `specs/003-openclaw-worker/spec.md` and `specs/004-live-run/spec.md` describe the setup.

## How it works

The rule across all three prototypes is the same: **the model proposes, code decides.** A deterministic core owns the state, and every reply about that state is checked against it.

- **The record.** Applications, mail, drafts and receipts live in one store. Status is computed from it. A missing reply is "unknown", never "rejected", and an attempt without a receipt is "possible effect", never "submitted".
- **The yes.** An approval binds to one exact action, version and recipient. A newer message, preview or revision voids it, and a bare yes with nothing pending does nothing.
- **Effects.** Each submit or send is idempotent and produces a receipt. An effect with an unknown outcome is reconciled with the target system, not retried.

How each prototype applies the rule:

- `scripted-demo`: `core.js` is a pure reducer and `scenes.js` feeds it scripted events. The state panel is rendered from the reducer, not hard-coded.
- `live-chat-demo`: Claude returns one typed intent per message. `intents.js` checks it against the current state and the fixtures, `core.js` applies only accepted events, and `voice.js` writes the reply from state. The thread is stored as an append-only event log in SQLite (`server/demo.db`).
- `openclaw-worker`: the browser talks to the core server (`server/serve.py`, `core/engine.py`), which holds the record, approvals, idempotency and receipts and has no model key. Each user message becomes one agent turn inside a pinned OpenClaw Gateway running in its own Docker container. The agent reaches the core's tools over MCP through an egress edge container with an allowlist. Submits and emails go to a local sandbox (`core/sandbox.py`) that no employer can see.

The deck proposes the same shape for Tsenta: Tsenta's core above, swappable agents below, reachable from MCP-compatible hosts, with proactive wake where a host supports it and Tsenta's own channels elsewhere.

## Status and limits

- **Fictional data only.** Every person, company, job, posting and email is invented. No real employer, mailbox or job portal is reachable from any prototype.
- **Not Tsenta's system.** These are local prototypes. None is integrated with Tsenta's product or data.
- **Real-agent test, October 13 and 14, 2026.** In `openclaw-worker`, an OpenClaw agent on Claude Haiku 5.5 passed 24 of 24 machine checks on its final run, with no false statement of record fact. It is a qualified pass: at one step it suggested giving a salary answer to the sender of a seeded injection email, and one record lookup returned an older resume version. The stress and security prompt sets have not been run live, and the full demo gate has not passed (deck slide 5).
- **Platform.** Live mode reads its key from the macOS Keychain, and some worker scripts (`openclaw/fill-browser.swift`, the Keychain route) are macOS-only. The operator scripts in `openclaw-worker/openclaw/` were written for one machine. Set `TSENTA_AUDIT_DIR` to choose where they write receipts.
- **Cost.** Live chat and live worker turns call the Anthropic API and are billed to whoever supplies the key. The unit tests make no calls outside the local machine.
- **Deck.** Only the PPTX is included. Slide 7 tells its career story through a fictional candidate.
- **Code comments** still carry short review tags from development (for example `551 v147` or `TRUTH0322`). They are labels, not links to anything in this repo.

## License

No license has been chosen yet; see `LICENSE`. Third-party notices are in `THIRD_PARTY_NOTICES.md`.
