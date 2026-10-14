# Tsenta agent worker demo (OpenClaw on synthetic data)

Spec: `specs/003-openclaw-worker/spec.md`. Everything here is fictional: 10 invented personas, postings, applications
and mail (`fixtures/seed.json`, the stress fixture, schema `tsenta-demo-fixture/1`). Submits and emails go to a
local sandbox; no employer, mailbox or portal is reachable.

```
browser (index.html, app.js)  ->  server/serve.py :8550  (core: record, approvals, idempotency, reset, receipts; no model key)
                                     |  one worker turn per message      ^  tools as MCP (POST /mcp, bearer token per boot)
                                     v                                   |
                                  OpenClaw Gateway (pinned, isolated; NOT installed yet: the worker reports offline)
core/engine.py  the record and every rule      core/sandbox.py  ATS + mailbox sink :8551, own SQLite log
core/profile.py FAKE profile source (real modes refuse)   core/worker.py  Gateway client (fails closed until wired)
```

Run: `python3 -m core.sandbox --port 8551 --db run/sandbox.db` and `PORT=8550 python3 -m server.serve`.
Tests: `python3 -m unittest discover tests`; the stress fixture's oracle (fixture not included here):
`CORE_FACTORY=tests.oracle_factory:make PYTHONPATH=.:<stress-fixture> python3 -m unittest test_contract`.
