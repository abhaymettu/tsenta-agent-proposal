# Plan 001

- `index.html`, `styles.css`, `app.js` (UI), `core.js` (pure state core, UMD so node can test it), `scenes.js` (scripted scenes as data: agent/user lines plus core events).
- `server/serve.py`: stdlib static server plus `POST /api/agent` per docs/CONTRACT.md. Mock mode by default; live Claude mode only when a Keychain key and a verified balance are configured (the cost cap was removed by the owner on 2026-10-13).
- `intercept/`: later, own-session client-side reroute of tsenta.com's in-app assistant chat to localhost. Read-only toward Tsenta.
- Motion: CSS transitions only, bubbles enter with opacity + translateY(8px) + scale(0.98) at 260ms cubic-bezier(0.23,1,0.32,1); typing indicator; state-panel row highlight on change. Reduced motion = opacity only.
- Tests: `tests/core.test.js` exercises every fixture rule against the reducer.
