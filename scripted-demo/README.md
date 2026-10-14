# Tsenta personal agent: iMessage simulation

A private, local vision prototype. It looks like an iMessage thread with a Tsenta agent and plays five scripted scenes. Everything is synthetic, and nothing is sent anywhere. This is a proposed direction for discussion, not something Tsenta has adopted.

## Run

```sh
python3 server/serve.py
```

Then open http://127.0.0.1:8521/. Opening `index.html` directly also works, in scripted mode only.

`/api/status` reports `mode: mock` and `spentUsd: 0` unless live mode is set up.

Controls: **Space**, **Enter** or **→** to advance, **1** to **5** to jump to a scene, **←** for the previous scene, **R** to restart, **S** to show or hide the agent-state panel. At phone width, tap the thread to advance.

Typing: the composer is pre-filled with the candidate's next scripted line, and Send plays it. Anything else typed gets a canned reply tagged "scripted · mock" that says what the demo cannot do. It never changes state and never claims an action (pause, send, undo).

Deep links: `?scene=3` starts at scene 3 with scenes 1 and 2 already in the thread. `?scene=3&step=all` shows scene 3 complete. `&state=open` opens the state panel.

## The five scenes

1. **Asks before it assumes.** Goal first, then sources it can and cannot see, then permissions (on its own, asks you, never).
2. **Says unknown instead of guessing.** Receipt versus attempt. Pausing mid-submit leads to "possible effect", then a reconcile, never a blind retry.
3. **A yes means one exact thing.** An ambiguous invite stays unlinked. Draft v1 becomes v2. A new match arrives, and the "yes" still binds to A1 v2 for Jordan.
4. **Retires stale work.** The candidate replies by hand, so the draft and nudge retire. Then a confirmation (rev 1), a cancellation (rev 2), and a late copy of rev 1 that is ignored. The state panel shows sent applications as "no reply yet, waiting" (Halyard ML Platform: "employer replied").
5. **Silence isn't rejection.** Healthy-and-quiet versus a disconnected mailbox, and one reversible route change with no diagnosis. After School Outlook disconnects, the panel shows those applications as "reply unknown, School Outlook disconnected". Nothing is ever marked rejected.

## Timing (measured)

`node tests/dryrun.mjs` plays all five scenes at phone width at the app's own speed. It presses Next only once the app is idle, so it never skips the typing indicator or pauses. Three runs on 2026-10-12 at about 22:56 CDT, against the mock server on 8521:

| Scene | Playback | Presses (sends) |
|---|---|---|
| 1 | 5.4 s | 2 |
| 2 | 6.2 s | 1 |
| 3 | 6.7 s | 3 |
| 4 | 6.4 to 6.5 s | 0 |
| 5 | 5.8 to 5.9 s | 2 |
| Total | 30.5 to 30.6 s | 8 sends + 4 scene advances |

That is machine time only: typing dots and pauses are set in `app.js` (agent typing time is reply length × 11 ms, clamped to 550 to 1300 ms; 450 ms system lines, 500 ms asides, 160 ms cards, 250 ms after each send). Everything else in the slot is the presenter talking. The meeting script budgets about three minutes for the walkthrough, which leaves about two and a half minutes of talk, roughly 30 seconds per scene.

Short version, if the slot is cut: open `?scene=3`, play it, then press **5**. Scene 3 ("a yes means one exact thing") and scene 5 ("silence isn't rejection") take 12.5 s of playback together, and the jump plays the skipped scenes into the thread instantly, so the state stays complete. This choice is a suggestion, not a measured result.

## Backup video (offline)

`node tests/record.mjs <outDir>` records two silent phone-width MP4s from the running mock server with headless Chrome. It refuses to run unless `/api/status` reports `mode: mock`. Every frame carries a strip reading "SIMULATION · MOCK · LIVE MODEL OFF / Synthetic data. Nothing is sent." The script also writes `desktop-scene1..5.png` (1440x900, state panel open).

- `full.mp4`: all five scenes, 55.2 s (2026-10-13 02:23 run).
- `short.mp4`: `?scene=3`, then key 5, 26.2 s.

The app plays at its own speed. On top of that, the recording holds each composer line for 1.2 s before Send and each finished scene for 2.5 s. The full video is about two minutes shorter than the meeting script's three-minute walkthrough, so the presenter pauses the player or talks over it. It shows the scripted path only: no typed input, no state panel at phone width, and no audio.

## What is hard-coded

- All dialogue, people (Maya, Jordan), employers (Halyard, Northwind, Lumen Data, Fathom Robotics, Quill Health), emails, times and outcome data. They live in `scenes.js` and are all synthetic.
- The events each scene feeds into the state core.
- The canned replies for typed text in scripted mode (`MOCK` in `server/serve.py`).

What is not hard-coded: the cards in the thread and the right-hand "What code owns" panel are rendered from `core.js`. That is a deterministic reducer which enforces the rules: a yes binds to the exact action, version and recipient; an ambiguous invite is not force-linked; manual completion retires drafts and timers; stale revisions are ignored; restart produces unknown-effect plus reconcile; route changes are reversible; a duplicate receipt is counted once; a permission change voids an open approval and blocks placing an approval from older permissions; reply status is waiting, unknown (source down) or replied, never rejected. `node --test tests/` checks those rules.

## Modes

- **Scripted** (default): no network, no key. Typed text gets canned replies (above).
- **Live** (`server/`, see `docs/CONTRACT.md`): typed messages go to Claude through the local server. The model proposes; `core.js` decides. It is off until the SDK is loaded, a Keychain key exists and `server/live.json` records a verified balance and a cost cap; the UI says which mode is running. It has never made a real call.

## Checks

```sh
node --test tests/                 # 14 state-core rules + every scene through the reducer
python3 -m unittest discover tests # 3 server checks (canned replies)
node tests/e2e.mjs [screenshotDir] # headless Chrome at 390px: plays all scenes, checks overflow, then
                                   # R / Space / 4 / Left arrow and typed text, asserted on core state
node tests/dryrun.mjs              # timed dry-run at the app's own speed (see Timing)
node tests/record.mjs <outDir>     # backup videos + desktop pixels, mock mode only (see Backup video)
```

| Claim in the demo | Code-level check |
|---|---|
| A yes binds to the asked action, version and recipient | yes binds to the asked version; yes after a newer draft does not approve the stale question; a changed recipient voids the question |
| A model-proposed approval is checked by code | model intent with the wrong version is ignored; the model cannot approve the old recipient |
| Permission changes void old approvals | a permission change voids the open question; an approval granted under old permissions cannot be placed |
| A duplicate receipt is counted once | the same portal confirmation twice is counted once and creates no action or task |
| Healthy quiet vs disconnected, never rejected | silence with healthy mail is waiting, with a disconnected source is unknown, never rejected |
| Typed text in mock mode claims no action | test_action_words_claim_no_action; e2e typed check leaves core state unchanged |

Each core rule added on 2026-10-12 evening was checked by deleting it and watching its test fail. Everything is in memory: a reload restarts the demo.

## Grounding

Product facts come from the author's research notes on Tsenta (current state as of 2026-10-11). Tsenta already applies, tracks, syncs job mail and drafts recruiter replies, and its iMessage copy asks users to "reply 'apply'". The novelty shown here is one state carried across the search. No founder revenue or user numbers appear in the demo.
