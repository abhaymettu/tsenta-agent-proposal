"""Sandbox "external" services: a local ATS and mailbox sink (548 s5, 551 s5). Nothing here can reach an employer:
submits and sends are rows in this process's own SQLite log, with a fake receipt.

Runs as its own process (`python3 -m core.sandbox --port 8551 --db run/sandbox.db`) so the OS boundary can wrap it.
The core talks to it through SandboxClient, which has the same methods as Sandbox (tests use Sandbox in-process).
A dedupe key is a single attempt, not an exactly-once guarantee: a repeat returns the first result.
"""
import json, sqlite3, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCHEMA = """
CREATE TABLE IF NOT EXISTS ats (key TEXT PRIMARY KEY, persona TEXT, receipt TEXT, receipt_at TEXT, mode TEXT,
  attempts INTEGER NOT NULL DEFAULT 1, payload_hash TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS outbox (key TEXT PRIMARY KEY, persona TEXT, recipient TEXT, v INTEGER, body_hash TEXT,
  attempts INTEGER NOT NULL DEFAULT 1, at TEXT);
CREATE TABLE IF NOT EXISTS log (id INTEGER PRIMARY KEY, op TEXT, key TEXT, persona TEXT, result TEXT, at TEXT);
"""


class Sandbox:
    def __init__(self, db=':memory:'):
        self.lock = threading.Lock()
        self.con = sqlite3.connect(db, check_same_thread=False, isolation_level=None)
        self.con.executescript(SCHEMA)

    def _log(self, op, key, persona, result, at):
        cur = self.con.execute("INSERT INTO log(op, key, persona, result, at) VALUES(?,?,?,?,?)", (op, key, persona, json.dumps(result), at))
        return cur.lastrowid

    def seed(self, seed):
        """Reset to the fixture: confirmed applications have receipts; scripted faults are accepted without one."""
        with self.lock:
            self.con.execute("BEGIN")
            for t in ('ats', 'outbox', 'log'):
                self.con.execute(f"DELETE FROM {t}")
            faults = {f['key']: f for f in seed['ats_faults']}
            for a in seed['applications']:
                key = f"{a['actionId']}:{a['v']}"
                f = faults.get(key)
                if a['receipt'] == 'confirmed':
                    self.con.execute("INSERT INTO ats(key, persona, receipt, mode, at) VALUES(?,?,?,?,?)",
                                     (key, a['persona_id'], f"rcpt-{a['id']}", f['mode'] if f else None, a['applied']))
                elif f:  # accepted by the portal, receipt missing (timeout) or late
                    self.con.execute("INSERT INTO ats(key, persona, receipt, receipt_at, mode, at) VALUES(?,?,?,?,?,?)",
                                     (key, a['persona_id'], None, f['receipt_at'], f['mode'], a['applied']))
            self.con.execute("COMMIT")
            return {'ok': True}

    def submit(self, key, persona, payload_hash, clock, receipt):
        with self.lock:
            row = self.con.execute("SELECT receipt, persona FROM ats WHERE key=?", (key,)).fetchone()
            if row:
                if row[1] != persona:
                    return {'ok': False, 'error': 'not found'}
                self.con.execute("UPDATE ats SET attempts = attempts + 1 WHERE key=?", (key,))
                r = {'ok': True, 'receipt': row[0], 'counted_once': True} if row[0] else {'ok': True, 'receipt': None, 'held': 'accepted earlier, no receipt yet'}
            else:
                self.con.execute("INSERT INTO ats(key, persona, receipt, payload_hash, at) VALUES(?,?,?,?,?)", (key, persona, receipt, payload_hash, clock))
                r = {'ok': True, 'receipt': receipt}
            r['log_id'] = self._log('submit', key, persona, r, clock)
            return r

    def status(self, key, persona, clock):
        with self.lock:
            row = self.con.execute("SELECT receipt, receipt_at, mode, persona FROM ats WHERE key=?", (key,)).fetchone()
            if not row or row[3] != persona:
                r = {'ok': True, 'receipt': None, 'held': 'no submission on record'}
            elif row[0]:
                r = {'ok': True, 'receipt': row[0]}
            elif row[2] == 'timeout_after_accept' or (row[2] == 'late_receipt' and row[1] and clock >= row[1]):
                rc = f"rcpt-{key.split(':')[0]}"
                self.con.execute("UPDATE ats SET receipt=? WHERE key=?", (rc, key))
                r = {'ok': True, 'receipt': rc, 'reconciled': True}
            else:
                r = {'ok': True, 'receipt': None, 'held': 'no receipt yet; not resubmitted'}
            r['log_id'] = self._log('status', key, persona, r, clock)
            return r

    def send(self, key, persona, recipient, v, body_hash, clock):
        with self.lock:
            if not recipient.endswith('.example'):
                return {'ok': False, 'error': 'sandbox delivers to .example addresses only'}
            row = self.con.execute("SELECT persona FROM outbox WHERE key=?", (key,)).fetchone()
            if row:
                self.con.execute("UPDATE outbox SET attempts = attempts + 1 WHERE key=?", (key,))
                r = {'ok': True, 'counted_once': True}
            else:
                self.con.execute("INSERT INTO outbox(key, persona, recipient, v, body_hash, at) VALUES(?,?,?,?,?,?)", (key, persona, recipient, v, body_hash, clock))
                r = {'ok': True, 'delivered_to': 'local outbox only'}
            r['log_id'] = self._log('send', key, persona, r, clock)
            return r

    def outbox(self, persona=None):
        q = "SELECT key, persona, recipient, v FROM outbox" + (" WHERE persona=?" if persona else "") + " ORDER BY at, key"
        return [dict(zip(('key', 'persona', 'to', 'v'), r)) for r in self.con.execute(q, (persona,) if persona else ())]

    def submissions(self, key):
        """How many submit attempts the portal saw for a key, and whether it holds a receipt (gate evidence)."""
        row = self.con.execute("SELECT attempts, receipt FROM ats WHERE key=?", (key,)).fetchone()
        return {'rows': 1 if row else 0, 'attempts': row[0] if row else 0, 'receipt': row[1] if row else None}

    def log_since(self, after_id):
        return [dict(zip(('id', 'op', 'key', 'persona', 'result'), (r[0], r[1], r[2], r[3], json.loads(r[4]))))
                for r in self.con.execute("SELECT id, op, key, persona, result FROM log WHERE id > ? ORDER BY id", (after_id,))]


METHODS = ('seed', 'submit', 'status', 'send', 'outbox', 'submissions', 'log_since')


class SandboxClient:
    """The core's view of the sandbox process: same methods, JSON over loopback HTTP."""

    def __init__(self, url):
        self.url = url.rstrip('/')

    def __getattr__(self, name):
        if name not in METHODS:
            raise AttributeError(name)

        def call(*args):
            req = urllib.request.Request(f"{self.url}/{name}", data=json.dumps(args).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        return call


def serve(port, db):
    box = Sandbox(db)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            name = self.path.strip('/')
            if name not in METHODS:
                self.send_error(404)
                return
            args = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'[]')
            body = json.dumps(getattr(box, name)(*args)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8551)
    p.add_argument('--db', default='run/sandbox.db')
    a = p.parse_args()
    serve(a.port, a.db)
