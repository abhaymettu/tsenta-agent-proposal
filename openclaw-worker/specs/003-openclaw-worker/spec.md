# 003: OpenClaw worker on synthetic data (core unit first)

Owner 18:35/18:36/18:42:53, parent 18:38, operator 18:48. Contracts: 548 `crosscheck/OPENCLAW-DEMO-DECISION.md`
(architecture, tools s4, invariants s7, receipts s8, lifecycle s9, gates s11, prompts s12) and 551
`hermes-fit/OPENCLAW-WORKER-CONTRACT.md` (boundaries B1 to B10, tool surface s5, gates G-a to G-i). Fixture: 552
`stress-fixture/seed.json` (schema `tsenta-demo-fixture/1`, sha256 9141703f...), vendored at `fixtures/seed.json`.

## What this unit builds (no OpenClaw installed; 551 18:54 allows it)
1. **Core** (`core/engine.py`): the record, persona scoping, the affirmative grammar, single-use approval tokens
   bound to `{persona, action key, version, payload hash}`, idempotency `actionId:version`, reset, per-call receipts.
   The model never changes state except through a tool handler. There is no approve tool. The core makes no model calls.
2. **Sandbox** (`core/sandbox.py`): the local ATS and mailbox sink with its own SQLite log, scripted fault modes
   (timeout after accept, late receipt, duplicate key). It runs as its own process so the OS boundary (551 s9) can
   wrap it. A dedupe key is a single attempt, not an exactly-once claim; an ambiguous outcome is UNKNOWN and never
   retried.
3. **Tool server**: one MCP endpoint (`POST /mcp`, JSON-RPC: initialize, tools/list, tools/call) on 127.0.0.1 with a
   per-boot bearer token. A tool call is only accepted while the core has an active turn, and it runs as that turn's
   persona (a `persona_id` argument is refused).
4. **Worker client** (`core/worker.py`): one OpenClaw Gateway turn per user message. Until the Gateway is configured
   it reports OFFLINE and the turn fails closed ("worker offline, nothing was done"). There is no direct-model fallback.
5. **Profile source**: FAKE (fixture) is the default and the only mode that runs. REAL-READ and REAL-WRITE refuse to
   start without config, a start flag, a vault credential and a written allowlist (551 s2a; OAuth not obtained).
6. **UI**: the 8527 UI, reworded for a fictional persona and sandbox effects, on port 8550. Keys: R reset, S debug,
   `]` next persona.

## Tool names
548 s4 names are implemented, because 552's fixture and oracle bind them. Mapping to 551 s5: search_jobs/get_job ->
`record_search kind=postings` / `record_get`; get_profile -> `profile_get`; draft_resume -> `resume_variant`;
draft_reply -> `draft_create`/`draft_revise`; submit_application -> `ats_submit`; send_mail -> `mail_send_draft`;
schedule_check -> not in this unit (open).

## Acceptance for this unit
- 552's 35 oracle tests pass against this core (`CORE_FACTORY=tests.oracle_factory:make`).
- Own tests: persistence across a core restart (state, pending preview, tokens void on a newer message), reset
  (reseed, generation bump, outbox and preferences empty), payload-hash binding, MCP auth and turn scoping, fail
  closed with the Gateway offline, no model import in the core.
- 8527, 8526 and 8521 untouched (pid, port, 8527 DB hash 59b800d0...).

## Not in this unit
OpenClaw install and config (551 B4, B7 to B9 pending; Docker daemon not running), G-c/G-e/G-h confinement proofs,
the 23-prompt live run, pixels, REAL modes.
