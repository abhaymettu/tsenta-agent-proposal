# Working on this repo

Instructions for anyone, human or coding agent, changing the code here. The product overview is in `README.md`.

## Layout

Four independent folders: `pitch/`, `scripted-demo/`, `live-chat-demo/`, `openclaw-worker/`. Nothing is shared between them. Change one folder at a time and run that folder's tests.

## Tests

| Folder | Command |
|---|---|
| `scripted-demo/` | `node --test tests/*.test.js && python3 -m unittest discover tests` |
| `live-chat-demo/` | `node --test tests/*.test.js && python3 -m unittest discover tests` |
| `openclaw-worker/` | `python3 -m unittest discover tests && node --test openclaw/edge.test.mjs` |
| `pitch/` | `uv run --no-project --with python-pptx python build/build_deck.py` must finish and report 29 slides |

The unit tests are deterministic and make no external network or model calls. Keep them that way. Scripts that make paid calls (`tests/http_smoke.mjs`, `tests/live_eval.mjs`, `openclaw/run_prompts.py` in live mode) are run by hand, never from the test suite.

## Product rules the code enforces

Do not weaken these without changing the spec in `specs/` first.

1. The model proposes and code decides. A model reply never changes state directly.
2. A yes binds to one exact action, version and recipient. Anything newer voids it.
3. Unknown stays unknown. Silence is never a rejection, and an attempt without a receipt is never "submitted".
4. An effect with an unknown outcome is reconciled, never retried blindly.
5. Replies about status come from the record, not from the model's memory.

## Data and secrets

- All fixtures are fictional. Do not add real names, emails, phone numbers, addresses, resumes or account data, in fixtures, tests, screenshots or the deck.
- Never put an API key or token in a file, an environment file, a test or a commit. Live mode reads the key from the macOS Keychain; the worker receives it at run time in memory only.
- Local runtime state (`run/`, `server/demo.db`, `server/live.json`, `server/.spend.json`) is gitignored. Keep it that way.

## The deck

Edit `pitch/build/content.py` (slide text) or `pitch/build/notes.py` (speaker notes), rebuild, and check every changed slide by rendering it before replacing `pitch/Tsenta-Pitch.pptx`. Every claim needs a source in the notes or the appendix slides.

## Specs

Feature specs live in each folder's `specs/` directory. Start a new feature with a spec, then the code and tests.
