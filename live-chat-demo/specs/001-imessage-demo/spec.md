# Spec 001: Tsenta personal-agent iMessage demo (simulation)

## Why
The owner wants to show Tsenta's founders a working vision of a personal job-search agent over iMessage. Tsenta already texts apply/status updates ("reply 'apply' to confirm"), so that is not the novelty. The novelty is one state carried across the search: goal and constraints, then route, receipt (confirmed vs unknown), accepted next task, manual completion, and an honest stage or closure.

## Users and situation
The owner presents in a meeting on a laptop or a phone. One presenter, tap-through, can restart.

## Requirements
- R1 An iMessage-like thread at phone width (390px) and inside a phone frame on desktop.
- R2 SIMULATION label visible at all times; synthetic data note.
- R3 Five scenes, each with a one-line principle, advanced by one tap or key (Next / Space / Right arrow); jump to any scene; Reset.
- R4 A visible "agent state" panel showing what deterministic code owns (goal, sources, opportunities, tasks, actions with version, event log including ignored stale events).
- R5 Scene fixtures (from the SCOPE UPDATE): two roles at one employer, ambiguous invite not force-linked; text "yes" binds to exact action/recipient/version; manual availability retires a stale draft; confirmation then cancellation; delayed old event cannot revive a reminder; healthy-silent vs disconnected source; pause/restart gives "unknown, possible effect" and reconcile instead of retry; source coverage unknowns visible; one reversible choice with no rejection diagnosis.
- R6 Mock mode works offline with no server features. Live mode (later) lets the presenter type free text answered by Claude through server/, with the state core validating any proposed intent.
- R7 Deep link `?scene=N&step=all` renders a scene complete (for screenshots and recovery mid-meeting).
- R8 Reduced motion respected.

## Out of scope
Real sends, accounts, PhD/errands/employer marketplace (may appear only as a labelled future), sharing with Tsenta.

## Acceptance
`python3 server/serve.py` serves the app; all five scenes play end to end at 390px; `node --test tests/` passes; screenshots exist (not part of this export).
