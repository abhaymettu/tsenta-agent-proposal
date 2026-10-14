#!/usr/bin/env python3
"""Serve the prototype on 127.0.0.1 and answer the agent endpoint (docs/CONTRACT.md).

Scripted (mock) mode by default: typed messages get a canned reply from MOCK. Live mode needs all three:
  1. the `anthropic` SDK (run with: uv run --with anthropic server/serve.py),
  2. a key in macOS Keychain, service "tsenta-prototype-anthropic" (never in a file or env),
  3. server/live.json with {"balance_verified": "<when and by whom>", "cap_usd": <hard cap>}.
The UI falls back to the script on any non-200.
"""
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8521"))
KEYCHAIN_SERVICE = "tsenta-prototype-anthropic"
MODEL = "claude-opus-5-5"
PRICE_IN, PRICE_OUT = 4.00 / 1e6, 20.00 / 1e6  # USD per token, claude-opus-5-5
SPEND_FILE = os.path.join(HERE, ".spend.json")
LOCK = threading.Lock()

SYSTEM = """You are the Tsenta personal job-search agent inside a SIMULATED iMessage demo. Every person, employer and message is synthetic.
You text a candidate named Maya. Write like a good iMessage: one to three short sentences, plain words, no markdown, no em dashes, no emoji.
The JSON state you receive is the source of truth, owned by deterministic code. Never claim anything the state does not show. If the state says unknown, say unknown. Silence from an employer is not a rejection.
You never send anything, apply anywhere, or accept or decline interviews yourself. You may only propose an intent, which code will accept or reject:
- "approve" with the exact actionId and version from `pending`, only when Maya clearly approves that open question;
- "pause" or "resume"; "route_choose" with `to` equal to state.route.proposed; "route_undo";
- otherwise "none".
If Maya asks for something outside job search, say this demo only covers her search."""

# Scripted replies for typed messages in mock mode: (trigger words or phrases, reply). First match wins.
MOCK = [
    (("status", "update", "progress", "where", "how's"), "Scripted reply: I can't read a real status in this demo. The real agent answers from tracked state: what's confirmed, what's unknown, and what's waiting on you. Nothing guessed."),
    (("interview", "schedule", "calendar"), "I never accept or decline an interview time for you. I draft a reply with the times you gave me, and you send it."),
    (("yes", "ok", "okay", "sure", "do it", "approve"), "A yes covers one exact thing: the action, the version you saw, and the recipient. A typed yes here approves nothing; the scenes show how it works."),
    (("apply", "send", "submit"), "Inside your filters the agent applies on its own. Anything that goes out from your own account, it asks first. Nothing is applied or sent from this demo."),
    (("rejected", "ghosted", "heard back", "silence", "no reply"), "Silence isn't rejection. Only the company can close an application; until then it stays open with how long it's been."),
    (("pause", "stop", "hold"), "Pausing stops anything new from going out, and anything mid-flight comes back as confirmed or unknown, never guessed. A typed pause here changes nothing; scene 2 shows it."),
    (("undo", "revert"), "Route changes undo exactly. A typed undo here changes nothing; scene 5 shows it."),
]
MOCK_DEFAULT = "This demo is scripted, so typed messages get canned answers about how the agent behaves: ask about status, applying, interviews, silence, pausing or undo. Understanding anything you type needs live mode, which is off."


def mock_reply(text):
    t = text.lower()
    words = set(re.findall(r"[a-z']+", t))
    for keys, reply in MOCK:
        if any((k in t) if " " in k else (k in words) for k in keys):
            return reply
    return MOCK_DEFAULT


SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "intent": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["none", "approve", "pause", "resume", "route_choose", "route_undo"]},
                "actionId": {"type": "string"},
                "version": {"type": "integer"},
                "to": {"type": "string"},
            },
            "required": ["type", "actionId", "version", "to"],
            "additionalProperties": False,
        },
    },
    "required": ["reply", "intent"],
    "additionalProperties": False,
}


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def keychain_key():
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def status():
    live = read_json(os.path.join(HERE, "live.json"), None)
    spent = read_json(SPEND_FILE, {}).get("usd", 0.0)
    base = {"mode": "mock", "model": MODEL, "spentUsd": spent}
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return dict(base, reason="SDK not loaded (run with uv run --with anthropic)")
    if not live or not live.get("balance_verified") or not live.get("cap_usd"):
        return dict(base, reason="credit balance not verified (server/live.json)")
    if not keychain_key():
        return dict(base, reason="no key in Keychain")
    cap = float(live["cap_usd"])
    if spent >= cap:
        return dict(base, mode="capped", capUsd=cap, reason="cost cap reached")
    return dict(base, mode="live", capUsd=cap)


def call_claude(req):
    import anthropic

    client = anthropic.Anthropic(api_key=keychain_key())
    context = json.dumps({"scene": req.get("scene"), "pending": req.get("pending"), "state": req.get("state")})
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": f"<state>{context}</state>\n\nMaya: {req.get('userText', '')[:500]}"}],
    )
    usd = resp.usage.input_tokens * PRICE_IN + resp.usage.output_tokens * PRICE_OUT
    with LOCK:
        spend = read_json(SPEND_FILE, {"usd": 0.0, "calls": 0})
        spend["usd"] = round(spend["usd"] + usd, 6)
        spend["calls"] += 1
        with open(SPEND_FILE, "w") as f:
            json.dump(spend, f)
    if resp.stop_reason == "refusal":
        return {"mode": "live", "reply": "I can't help with that one here.", "intent": None, "model": MODEL, "spentUsd": spend["usd"]}
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))
    intent = data["intent"] if data["intent"]["type"] != "none" else None
    return {
        "mode": "live", "reply": data["reply"], "intent": intent, "model": MODEL,
        "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        "spentUsd": spend["usd"],
    }


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):  # quiet: no bodies, headers or query strings in logs
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            return self.send_json(200, status())
        if self.path.startswith("/server/"):  # never serve server files (spend, live.json)
            return self.send_json(404, {"error": "not found"})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/agent":
            return self.send_json(404, {"error": "not found"})
        st = status()
        try:
            req = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 200_000)))
            if st["mode"] != "live":
                return self.send_json(200, dict(st, reply=mock_reply(str(req.get("userText", ""))[:500]), intent=None))
            return self.send_json(200, call_claude(req))
        except Exception as e:  # upstream or parse failure: UI falls back to the script
            sys.stderr.write("agent error: %s\n" % type(e).__name__)
            return self.send_json(502, {"error": type(e).__name__})


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Tsenta iMessage prototype (simulation): http://127.0.0.1:{PORT}/  mode: {status()['mode']}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
