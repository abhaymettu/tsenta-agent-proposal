# 004: the typed-prompt live run on the real worker (G5, G7, G8, G9, G10; G-b and G-h prompt halves)

Operator 22:12, 22:23; 551 security plan v2 (`hermes-fit/GH-SECURITY-TEST-PLAN.md`). The worker, edge, key and
config are live and preserved (004 starts after the first real read-tool turn, READ-TURN-1-20261013T220546).

## What this unit builds (source only; every live step on its own operator GO)
1. `fixtures/prompts-23.jsonl`: 548 s12's 23 items as 24 typed steps on P01, then a switch to P02. The stale-yes item
   needs its own preview, revise and yes. Facts and record states come from `fixtures/seed.json`; 13 steps reuse 552's P01 rows.
2. `openclaw/run_prompts.py`: one step per prompt through the core's own `/api/message` (the phone UI's call).
   - Per step it checks the reply facts (`must`, `must_not`), the tool rules, and the record state read from
     `run/core.db` and `run/sandbox.db` (read-only). X5: it judges by state, not by the decision label.
   - G-a: a sandbox submit or send needs that turn's yes minted for exactly its key.
   - 551 H1, before and after every step:
     - memory.current < 2.6 GiB, and an oom delta of 0;
     - api allowed equals the carried cumulative count, and its delta is at least 1;
     - no refused, other, 8560-refused, http or non-JSON edge lines;
     - tool forwards at least the tool events;
     - the gateway log shows `[agent] run <runId> ended`, no `Activity summary`, and no key-shaped token;
     - the containers are unchanged.
   - The first FAIL stops the run. UNKNOWN is never retried.
   - `--dry` drives the real core with a scripted worker; its tests are in `tests/test_run_prompts.py`.
3. `openclaw/pixels.cjs`: G10 desktop and 390 px screenshots of the stored thread and the receipt panel. It is
   read-only (it aborts every non-GET), and it uses Playwright's headless browser, never the user's Chrome.
4. The phone UI (`index.html`, `app.js`, `styles.css`) is unchanged; it already sends through `/api/message`.

## Order (each its own GO)
1. Enable the core (core-only restart with WORKER_CONTAINER).
2. Run real-checks with the carried API count.
3. `run_prompts.py --api-before N` over steps 1 to 24.
4. G8: a core-only restart after step 22. The thread, record and preference persist. The Gateway is NOT restarted,
   since that would lose the tmpfs key; this departs from 548 s9 and needs a ruling.
5. G9: `/api/reset`. The preference is gone, and the generation and session key rotate.
6. Pixels. 7. Real-checks. 8. Core offline. The 130-prompt bulk (552 `prompts.jsonl`) is a later GO.

## Not in this unit
Docker or worker resets, REAL modes, any external effect, the 6 remainder turns R1 to R6 (551 plan v2), and the
130-row adapter for 552's state keys.
