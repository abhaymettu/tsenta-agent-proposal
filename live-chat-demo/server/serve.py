#!/usr/bin/env python3
"""Serve the prototype on 127.0.0.1 and answer the agent endpoint (docs/CONTRACT.md).

Scripted (mock) mode by default: typed messages get a canned reply from MOCK. Live mode needs all three:
  1. the `anthropic` SDK (run with: uv run --with anthropic server/serve.py),
  2. a key in macOS Keychain, service "tsenta-prototype-anthropic" (never in a file or env),
  3. server/live.json with {"balance_verified": "<when and by whom>"}.
There is no money cap; stop and report if credits run low.
Spend is always recorded in the ledger (an estimate from usage tokens, not a bill).

Demo backend (live variant): the scene-6 conversation lives in SQLite (server/demo.db, TSENTA_DB), not the browser.
  GET  /api/thread   state, live messages and the agent-message count
  POST /api/message  {text, key, seen}: one message through the rules; idempotent on key
  POST /api/reset    back to the labelled seed data (scenes 1 to 6)
Rules run in server/worker.js (the same core.js, intents.js, voice.js as the browser). Everything stays on this machine.
POST /api/agent stays for tests/live_eval.mjs: it proposes an intent for a supplied state and stores nothing.
"""
import contextlib
import fcntl
import http.server
import json
import os
import re
import select
import shutil
import sqlite3
import urllib.parse
import uuid
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8521"))
KEYCHAIN_SERVICE = "tsenta-prototype-anthropic"
# Live variant: a fast model answers; Opus is review-only. Override with TSENTA_MODEL for measurement.
MODEL = os.environ.get("TSENTA_MODEL", "claude-haiku-5-5")
# USD per million tokens (input, output), from platform.claude.com/docs/en/about-claude/pricing (fetched 2026-10-13).
# Haiku 5.5 rate is for prompts up to 100k tokens; requests here are a few thousand.
PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.00, 10.00), "claude-opus-5-5": (4.00, 20.00)}
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}  # server-side refusal fallback documented for these
# One ledger can be shared across servers (TSENTA_SPEND_FILE) so the estimate covers all of them.
SPEND_FILE = os.environ.get("TSENTA_SPEND_FILE", os.path.join(HERE, ".spend.json"))
LOCK = threading.Lock()  # within this process; ledger_lock() below also serializes against other processes using it

SYSTEM = """You are the intent picker for the Tsenta personal job-search agent in a SIMULATED iMessage demo. Everything is synthetic.
You never write what the agent says. Code writes every reply from state. You return exactly one intent for Maya's latest message.

Pick:
- "answer" with topic: "replies" (did anyone reply / was I rejected / heard back; set oppId if she names one application), "receipts" (how many applied / did it go through, when nothing needs checking), "interviews", "open_items" (what do you need from me), "sources" (what can you see / connected), "permissions" (what can you do on your own), "cannot" (she asks you to send, accept, decline or schedule something), "scope" (not about her job search), "unclear".
- "pause" / "resume": she asks to pause or resume Tsenta.
- "draft" (taskId, body): she asks for a reply on a task whose id starts with "T-reply-" and status is "accepted" (open work). body is the full email in Maya's voice, using only details she gave or that state shows: never add a day, date, week, time, role or name she did not give.
- "redraft" (actionId, body): she wants an existing draft changed.
- "approve": she says yes to the open draft question in `pending` (code asks her to confirm; leave the other fields empty or copy them from pending).
- "reconcile" (oppId): she asks whether an application with receipt "unknown_effect" went through.
- "link" (interviewId, oppId): she says which candidate role an unlinked interview request is for.
- "manual_done" (taskId): she says she handled a task herself.
- "route_propose" (routeId from facts.routeOptions), "route_choose" (routeId, she accepts the open proposal), "route_undo" (she asks to undo).
- "show_status" (section "overview", "applications" or "setup"): she asks where things stand, or a picture answers better.
Leave unused fields as "" or 0. Code checks every proposal and asks Maya to confirm consequential ones; declines are expected."""

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


INTENT_TYPES = ["answer", "pause", "resume", "draft", "redraft", "approve", "reconcile", "link", "manual_done",
                "route_propose", "route_choose", "route_undo", "show_status"]
INTENT_FIELDS = {"topic": "string", "actionId": "string", "version": "integer", "recipient": "string", "epoch": "integer", "taskId": "string",
                 "body": "string", "oppId": "string", "interviewId": "string", "routeId": "string", "section": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "object",
            "properties": dict({"type": {"type": "string", "enum": INTENT_TYPES}}, **{k: {"type": t} for k, t in INTENT_FIELDS.items()}),
            "required": ["type"] + list(INTENT_FIELDS),
            "additionalProperties": False,
        },
    },
    "required": ["intent"],
    "additionalProperties": False,
}

def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


@contextlib.contextmanager
def ledger_lock():
    """Exclusive file lock beside the ledger. Held across read, call and write, so concurrent requests
    (in this or another server using this code) never lose each other's recorded spend."""
    # Lock wait (<= 4 s in total) plus the call stays under the browser's 25 s abort, so a request the UI gave up on
    # is not paid for later.
    deadline = time.monotonic() + 4  # one budget across both waits
    if not LOCK.acquire(timeout=4):
        raise TimeoutError("spend ledger busy")
    try:
        with open(SPEND_FILE + ".lock", "a") as f:
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("spend ledger busy")
                    time.sleep(0.1)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    finally:
        LOCK.release()


def read_ledger():
    """A missing ledger is zero; an unreadable one is an error, never silently zero (that would lose recorded spend)."""
    if not os.path.exists(SPEND_FILE):
        return {"usd": 0.0, "calls": 0}
    with open(SPEND_FILE) as f:
        return json.load(f)


def write_ledger(spend):
    tmp = SPEND_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(spend, f)
    os.replace(tmp, SPEND_FILE)  # atomic: a reader sees the old or the new ledger, never half of one


_key, _client = None, None


def keychain_key():
    """Read once per process and kept in memory only (never logged or written): no Keychain subprocess per request."""
    global _key
    if _key is None:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"], capture_output=True, text=True)
        _key = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    return _key


def api_client():
    """One client per process, so requests reuse its HTTPS connection instead of a new TLS handshake each time."""
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=keychain_key(), timeout=15.0, max_retries=0)  # one bounded attempt; each call also passes call_timeout() for the whole-request budget
    return _client


def status():
    live = read_json(os.path.join(HERE, "live.json"), None)
    try:
        spent = read_ledger().get("usd", 0.0)
    except (OSError, ValueError):
        return {"mode": "mock", "model": MODEL, "reason": "spend ledger unreadable"}
    base = {"mode": "mock", "model": MODEL, "spentUsd": spent}
    if MODEL not in PRICES:
        return dict(base, reason="no verified price for this model")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return dict(base, reason="SDK not loaded (run with uv run --with anthropic)")
    if not live or not live.get("balance_verified"):
        return dict(base, reason="credit not confirmed (server/live.json)")
    if not keychain_key():
        return dict(base, reason="no key in Keychain")
    return dict(base, mode="live")


BROWSER_ABORT_S = 25.0  # app.js aborts a request after this long
BUDGET_S = 22.0  # whole request on the server: lock wait plus every phase of the API call


def call_timeout(remaining):
    """Per-phase timeouts that add up to `remaining`, so the call ends before the browser gives up on it."""
    import anthropic
    return anthropic.Timeout(connect=2.0, write=2.0, pool=1.0, read=max(1.0, remaining - 5.0))


def call_claude(req, model=None, t0=None):
    t0 = t0 or time.monotonic()  # t0: when the request arrived, so a wait for TURN_LOCK counts too
    model = model or MODEL
    if model not in PRICES:  # before the paid call: an unpriced model's spend could not be recorded
        raise ValueError("no verified price for " + model)
    client = api_client()
    state = dict(req.get("state") or {})
    state["log"] = (state.get("log") or [])[-8:]  # recent events only: keeps the prompt small and fast
    context = json.dumps({"scene": req.get("scene"), "pending": req.get("pending"), "state": state, "facts": req.get("facts")})
    extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"} if model in FALLBACK_MODELS else {"betas": []}
    with ledger_lock():
        spend = read_ledger()
        remaining = BUDGET_S - (time.monotonic() - t0)
        if remaining < 6:  # too little time left to finish before the browser aborts: make no paid call
            raise TimeoutError("no time left for the call")
        resp = call_api(client, model, context, extra, str(req.get("userText", ""))[:500], call_timeout(remaining))
        pin, pout = PRICES[model]
        usd = (resp.usage.input_tokens * pin + resp.usage.output_tokens * pout) / 1e6
        spend["usd"] = round(spend["usd"] + usd, 6)
        spend["calls"] = spend.get("calls", 0) + 1
        spend.setdefault("byModel", {})[model] = round(spend.get("byModel", {}).get(model, 0.0) + usd, 6)
        write_ledger(spend)
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    if resp.stop_reason == "refusal":
        return {"mode": "live", "intent": {"type": "answer", "topic": "scope"}, "model": model, "usage": usage, "spentUsd": spend["usd"]}
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))
    # No reply text: the browser writes the agent's message from state (voice.js).
    return {"mode": "live", "intent": data["intent"], "model": getattr(resp, "model", model), "usage": usage, "spentUsd": spend["usd"]}


def call_api(client, model, context, extra, text, timeout):
    return client.beta.messages.create(
        model=model,
        timeout=timeout,
        max_tokens=2000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"<state>{context}</state>\n\nMaya: {text}"}],
        **extra,
    )


# ---------- demo backend: durable state in SQLite, rules in the node worker ----------
DB_FILE = os.environ.get("TSENTA_DB", os.path.join(HERE, "demo.db"))  # one server per file: run a second server with its own TSENTA_DB
PUBLIC = {"/", "/index.html", "/styles.css", "/app.js", "/core.js", "/scenes.js"}  # never server/, .git, tests
TURN_LOCK = threading.Lock()  # one message at a time, so each is checked against the state its predecessor left
WORKER_TIMEOUT_S = 5.0
DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, at TEXT NOT NULL, source TEXT NOT NULL, event TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, at TEXT NOT NULL, who TEXT NOT NULL, text TEXT NOT NULL,
  tag TEXT, card TEXT, card_state TEXT, key TEXT UNIQUE, response TEXT);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""
LOCAL_ONLY = "I can only answer: yes to my question, pause, resume, undo the route, status, details and setup."
HELD = "Claude isn't connected on this server, so " + LOCAL_ONLY


class Worker:
    """server/worker.js, kept running; one request at a time over JSON lines. Each reply echoes its request id, so a
    stray line is skipped instead of shifting every later reply; a reply that doesn't come in time kills the worker."""

    def __init__(self):
        self.p, self.lock, self.n, self.buf = None, threading.Lock(), 0, b""

    def _line(self, deadline):
        while b"\n" not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0 or not select.select([self.p.stdout], [], [], left)[0]:
                raise TimeoutError("worker did not answer")
            chunk = os.read(self.p.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("worker exited")
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        return line

    def call(self, timeout=WORKER_TIMEOUT_S, **msg):
        with self.lock:
            try:
                if self.p is None or self.p.poll() is not None:
                    self.p, self.buf = subprocess.Popen(["node", os.path.join(HERE, "worker.js")], stdin=subprocess.PIPE, stdout=subprocess.PIPE), b""
                self.n += 1
                self.p.stdin.write((json.dumps(dict(msg, id=self.n)) + "\n").encode())
                self.p.stdin.flush()
                deadline = time.monotonic() + timeout
                while True:
                    try:
                        out = json.loads(self._line(deadline))
                    except ValueError:
                        continue  # not a reply (a stray print): skip it
                    if isinstance(out, dict) and out.get("id") == self.n:
                        break
            except (TimeoutError, OSError, RuntimeError):
                if self.p is not None and self.p.poll() is None:
                    self.p.kill()  # our own child, hung or out of step: the next call starts a fresh one
                    self.p.wait(timeout=2)
                if self.p is not None:
                    self.p.stdin.close(); self.p.stdout.close()
                self.p = None
                raise
        if not out["ok"]:
            raise RuntimeError("worker: " + out["error"])
        return out["result"]


WORKER = Worker()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def db():
    con = sqlite3.connect(DB_FILE, timeout=5, isolation_level=None)  # explicit transactions below
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(DB_SCHEMA)
    return con


def meta(con, k, default=None):
    row = con.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
    return json.loads(row[0]) if row else default


def set_meta(con, k, v):
    con.execute("INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))


def reset(con):
    """Back to the labelled seed data: scenes 1 to 6 as events, no live messages."""
    seed = WORKER.call(op="seed")
    state = WORKER.call(op="replay", events=seed["events"])["state"]
    con.execute("BEGIN IMMEDIATE")
    try:
        for table in ("events", "messages", "meta"):
            con.execute(f"DELETE FROM {table}")
        con.executemany("INSERT INTO events(at, source, event) VALUES(?, 'seed', ?)", [(now(), json.dumps(e)) for e in seed["events"]])
        set_meta(con, "state", state)
        set_meta(con, "question", None)
        set_meta(con, "clock", seed["clock"])
        set_meta(con, "seeded_at", now())
        set_meta(con, "epoch", uuid.uuid4().hex)  # a fresh thread: no count from before a reset can match one after it
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise


def rebuild(con):
    """At start-up the event log is the source of truth: replay it and refresh the cached state."""
    events = [json.loads(r[0]) for r in con.execute("SELECT event FROM events ORDER BY seq")]
    seeded = [json.loads(r[0]) for r in con.execute("SELECT event FROM events WHERE source='seed' ORDER BY seq")]
    seed = WORKER.call(op="seed")
    if not events or seeded != seed["events"] or meta(con, "clock") != seed["clock"]:
        if events:
            sys.stderr.write("the demo data (scenes.js) changed since this thread was seeded: reseeding\n")
        return reset(con)
    state = WORKER.call(op="replay", events=events)["state"]
    con.execute("BEGIN IMMEDIATE")
    try:
        set_meta(con, "state", state)
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise


def seen_token(con):
    """What the browser echoes back: this thread's epoch and how many agent messages it holds."""
    return "%s:%d" % (meta(con, "epoch"), con.execute("SELECT COUNT(*) FROM messages WHERE who='them'").fetchone()[0])


def revision(con):
    return con.execute("SELECT (SELECT COALESCE(MAX(seq), 0) FROM events), (SELECT COALESCE(MAX(id), 0) FROM messages), (SELECT v FROM meta WHERE k='epoch')").fetchone()


def thread(con):
    if meta(con, "state") is None:
        reset(con)
    own = not con.in_transaction
    if own:
        con.execute("BEGIN")  # one snapshot: messages and state from the same moment
    try:
        return _thread(con)
    finally:
        if own:
            con.execute("COMMIT")


def _thread(con):
    rows = con.execute("SELECT id, at, who, text, tag, card, card_state FROM messages ORDER BY id").fetchall()
    msgs = [{"id": r[0], "at": r[1], "who": r[2], "text": r[3], "tag": r[4], "card": r[5], "cardState": json.loads(r[6]) if r[6] else None} for r in rows]
    return {"state": meta(con, "state"), "messages": msgs, "seen": seen_token(con), "clock": meta(con, "clock"),
            "seededAt": meta(con, "seeded_at"), "events": con.execute("SELECT COUNT(*) FROM events").fetchone()[0]}


def handle_message(req):
    """One message: rules first (no model call when code can answer), then Claude if needed, then one transaction."""
    text, key = str(req.get("text", "")).strip()[:500], str(req.get("key", ""))[:80]
    if not text or not key:
        return 400, {"error": "text and key are required"}
    t0 = time.monotonic()  # the request's budget starts now, so waiting for TURN_LOCK is inside it
    if not TURN_LOCK.acquire(timeout=BUDGET_S - 7):  # leaves over 6 s, so a message that needs Claude still gets a call
        return 503, {"error": "busy: another message is still being answered"}
    try:
        con = db()
        try:
            row = con.execute("SELECT response FROM messages WHERE key=?", (key,)).fetchone()
            if row:  # the same send twice (a retry) is answered once
                return 200, json.loads(row[0])
            if meta(con, "state") is None:
                reset(con)
            state, question, clock = meta(con, "state"), meta(con, "question"), meta(con, "clock")
            rev = revision(con)  # another process on the same file may write meanwhile; checked again before writing
            if str(req.get("seen")) != seen_token(con):
                question = None  # an agent message she hadn't seen (or a reset) came after the question: her message can't answer it
            r = WORKER.call(op="turn", state=state, question=question, text=text, clock=clock)
            tag = "reply written by code · no model call"
            if r.get("needModel"):
                st = status()
                if st["mode"] != "live":
                    r = {"state": state, "events": [], "reply": HELD, "question": None, "card": None, "kind": "held", "proposed": None, "waiting": None}
                    tag = "Claude not connected · " + st.get("reason", st["mode"])
                else:
                    try:
                        out = call_claude({"userText": text, "scene": 6, "state": state, "pending": state.get("pending"), "facts": r.get("facts")}, t0=t0)
                        if out["mode"] != "live" or not out.get("intent"):
                            raise RuntimeError(out["mode"])
                        else:
                            left = BROWSER_ABORT_S - 1 - (time.monotonic() - t0)  # the second rules call also ends before the browser gives up
                            r = WORKER.call(timeout=max(0.5, min(WORKER_TIMEOUT_S, left)), op="turn", state=state, question=question, text=text, intent=out["intent"], clock=clock)
                            tag = f"Claude · {str(out['model']).replace('claude-', '')} · {time.monotonic() - t0:.1f} s · reply written by code"
                    except Exception as e:  # nothing applied; the error message is the latest message, so no question survives
                        sys.stderr.write("agent error: %s\n" % type(e).__name__)
                        r = {"state": state, "events": [], "reply": "Live mode hit an error, so nothing was shown or changed. Try again.", "question": None, "card": None, "kind": "error", "proposed": None, "waiting": None}
                        tag = "live error"
            tag += {"yes": " · waiting for your yes", "which": " · asking which"}.get(r.get("waiting"), "")
            if r.get("proposed"):
                tag += " · proposal declined"
            con.execute("BEGIN IMMEDIATE")
            try:
                row = con.execute("SELECT response FROM messages WHERE key=?", (key,)).fetchone()
                if row:  # the same send answered meanwhile by another process on this file
                    con.execute("ROLLBACK")
                    return 200, json.loads(row[0])
                if revision(con) != rev:  # the thread changed under this answer: store nothing rather than lose an update
                    con.execute("ROLLBACK")
                    return 409, {"error": "the demo changed in another window; reload and send again"}
                at = now()
                cur = con.execute("INSERT INTO messages(at, who, text, key) VALUES(?, 'me', ?, ?)", (at, text, key))
                mine = cur.lastrowid
                con.executemany("INSERT INTO events(at, source, event) VALUES(?, 'live', ?)", [(at, json.dumps(e)) for e in r["events"]])
                con.execute("INSERT INTO messages(at, who, text, tag, card, card_state) VALUES(?, 'them', ?, ?, ?, ?)",
                            (at, r["reply"], tag, r.get("card"), json.dumps(r["state"]) if r.get("card") else None))
                note = ("Code accepted: " + ", ".join(e["type"] for e in r["events"])) if r["events"] else (
                    f"Claude proposed {r['proposed']}; code declined it" if r.get("proposed") else None)
                if note:
                    con.execute("INSERT INTO messages(at, who, text) VALUES(?, 'sys', ?)", (at, note))
                set_meta(con, "state", r["state"])
                set_meta(con, "question", r.get("question"))
                rows = con.execute("SELECT id, at, who, text, tag, card, card_state FROM messages WHERE id>=? ORDER BY id", (mine,)).fetchall()
                resp = {"messages": [{"id": x[0], "at": x[1], "who": x[2], "text": x[3], "tag": x[4], "card": x[5], "cardState": json.loads(x[6]) if x[6] else None} for x in rows],
                        "state": r["state"], "seen": seen_token(con)}
                con.execute("UPDATE messages SET response=? WHERE id=?", (json.dumps(resp), mine))
                con.execute("COMMIT")
            except BaseException:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
            return 200, resp
        finally:
            con.close()
    finally:
        TURN_LOCK.release()


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
            return self.send_json(200, dict(status(), backend=True))
        if self.path == "/api/thread":  # reads a snapshot; doesn't wait for a model call in progress
            con = db()
            try:
                if meta(con, "state") is None:
                    with TURN_LOCK:
                        return self.send_json(200, thread(con))
                return self.send_json(200, thread(con))
            finally:
                con.close()
        return super().do_GET()

    def send_head(self):  # GET and HEAD: only the page's own files, matched exactly (the disk ignores case; this doesn't)
        if urllib.parse.urlsplit(self.path).path not in PUBLIC:
            self.send_error(404)
            return None
        return super().send_head()

    def trusted(self):
        """JSON from this page only: a page on another site can't send JSON without a preflight this server never answers."""
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return ctype == "application/json" and self.headers.get("Origin") in (None, f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")

    def do_POST(self):
        if not self.trusted():
            return self.send_json(403, {"error": "JSON from this page only"})
        try:
            if self.path == "/api/message":
                req = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20_000)) or b"{}")
                return self.send_json(*handle_message(req))
            if self.path == "/api/reset":
                with TURN_LOCK:
                    con = db()
                    try:
                        reset(con)
                        return self.send_json(200, thread(con))
                    finally:
                        con.close()
        except Exception as e:
            sys.stderr.write("backend error: %s\n" % type(e).__name__)
            return self.send_json(500, {"error": type(e).__name__})
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
    if not shutil.which("node"):
        sys.exit("node is required: server/worker.js runs the demo's rules")
    with contextlib.closing(db()) as con:
        rebuild(con)  # the event log survives restarts; the cached state is rebuilt from it
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Tsenta iMessage prototype (simulation): http://127.0.0.1:{PORT}/  mode: {status()['mode']}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
