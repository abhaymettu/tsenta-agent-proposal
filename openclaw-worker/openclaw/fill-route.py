"""Loopback fill route for the model key (owner grant 19:01:16; never a Keychain read).

Serves one page on 127.0.0.1 at an unguessable path. The user pastes the Anthropic API key for this prototype into its
single password field, once, and the page POSTs the field as text/plain to the same path. This process checks the request completely first: the
path, Host == 127.0.0.1:<port> (DNS-rebinding guard), Origin == http://127.0.0.1:<port> exactly (a browser sends it; a
scripted client must too), Content-Type text/plain, a well-formed Content-Length within the cap, the whole body read
within the socket timeout, and a non-empty value. Only then does it pass the bytes to `openclaw/fill-key.sh <container>`
on stdin. It answers only {"filled": "yes"|"no"}. The value is never logged, never in argv or env, never written to a
host file, and nothing about it (hash or length) is recorded. Single use: the first request that passes the header
checks consumes the route, whatever its outcome, and the server then exits. It also exits after the idle timeout.
Agents never read the value: the agent only starts this route, and the user fills it (551 v25 RF-2).

Run: python3 -I openclaw/fill-route.py oc551-worker   (prints the URL; env FILL_TIMEOUT seconds, default 600)
"""
import html, json, os, secrets, socket, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BODY = 4096
FRAME_END = b'\nOC551-END\n'
PAGE = """<!doctype html><meta charset="utf-8"><meta name="referrer" content="no-referrer">
<title>Tsenta demo: model key fill (loopback, single use)</title>
<style>body{{font:15px system-ui;margin:3rem auto;max-width:28rem}}input,button{{font:inherit;padding:.5rem;width:100%;box-sizing:border-box;margin:.4rem 0}}</style>
<h1 style="font-size:1.1rem">Model key fill for {container}</h1>
<p>Paste the Anthropic API key for this prototype, once. It goes only into the worker's memory-only file. If the
browser offers to save it, choose Never.</p>
<form id="f"><input id="k" type="password" name="oc551-fill" autocomplete="off" aria-label="Key">
<button>Fill</button></form><p id="r" role="status"></p>
<script nonce="{nonce}">
document.getElementById('f').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const f = document.getElementById('f'), k = document.getElementById('k'), v = k.value.trim(); k.value = '';
  const r = document.getElementById('r');
  if (!v) {{ r.textContent = 'Empty; nothing sent.'; return; }}
  f.remove();  // single use: after this the page DOM holds no input and no value, only the status line
  try {{
    const res = await fetch(location.pathname, {{ method: 'POST', headers: {{ 'Content-Type': 'text/plain' }}, body: v }});
    r.textContent = 'filled: ' + ((await res.json()).filled === 'yes' ? 'yes' : 'no');
  }} catch (_) {{ r.textContent = 'filled: no (route closed)'; }}
}});
</script>"""


def make_server(container, fill_cmd=None, port=0, read_timeout=10):
    path = '/fill/' + secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(16)
    cmd = fill_cmd or [os.path.join(HERE, 'fill-key.sh'), container]
    done = threading.Event()

    class H(BaseHTTPRequestHandler):
        timeout = read_timeout  # socket timeout for every read, so a hung or slow POST cannot hold the route open

        def log_message(self, *a):  # never log requests (the path is a capability; bodies are secrets)
            pass

        def send(self, code, body=b'', ctype='application/json', extra=()):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def own(self):
            return f'127.0.0.1:{self.server.server_address[1]}'

        def do_GET(self):
            if self.path != path or done.is_set() or self.headers.get('Host') != self.own():
                return self.send(404)
            csp = f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'"
            self.send(200, PAGE.format(container=html.escape(container), nonce=nonce).encode(), 'text/html; charset=utf-8',
                      [('Content-Security-Policy', csp), ('X-Frame-Options', 'DENY')])

        def do_POST(self):
            no = b'{"filled": "no"}'
            if self.path != path or done.is_set():
                return self.send(404)
            if self.headers.get('Host') != self.own() or self.headers.get('Origin') != 'http://' + self.own() \
                    or not (self.headers.get('Content-Type') or '').startswith('text/plain') or 'Transfer-Encoding' in self.headers:
                return self.send(400, no)
            try:
                n = int(self.headers.get('Content-Length', ''))
            except ValueError:
                return self.send(400, no)
            if not 0 < n <= MAX_BODY:
                return self.send(400, no)
            done.set()  # single use from here on, whatever the outcome
            buf, got, ok = bytearray(n), 0, False
            try:
                view = memoryview(buf)
                while got < n:
                    k = self.rfile.readinto(view[got:])
                    if not k:
                        break
                    got += k
                view.release()
                value = bytes(buf).strip() if got == n else b''
                if value and b'\n' not in value and b'\r' not in value:  # complete, non-empty, one line: only now fill
                    # framed (551 M1): fill-key.sh publishes only if the stream ends with this exact line
                    r = subprocess.run(cmd, input=value + FRAME_END, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                    ok = r.returncode == 0
            except Exception:  # whatever happens, answer "no" and close; never a traceback with request data
                ok = False
            finally:
                buf[:] = bytes(len(buf))
                value = None
            try:
                self.send(200, json.dumps({'filled': 'yes' if ok else 'no'}).encode())
            except OSError:
                pass
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    srv = HTTPServer(('127.0.0.1', port), H)
    return srv, path


def serve(srv, idle_timeout, hard_exit=False):
    """Serve until the single fill or the idle timeout, then close the socket. With hard_exit (the CLI), a second timer
    ends the process outright if a stuck request ever keeps serve_forever from returning."""
    if hard_exit:
        hard = threading.Timer(idle_timeout + 90, lambda: os._exit(3))
        hard.daemon = True
        hard.start()
    timer = threading.Timer(idle_timeout, srv.shutdown)
    timer.daemon = True
    timer.start()
    try:
        srv.serve_forever()
    finally:
        timer.cancel()
        srv.server_close()


def main():
    container = sys.argv[1] if len(sys.argv) > 1 else ''
    if container not in ('oc551-worker', 'oc551-edge'):
        sys.exit('usage: fill-route.py oc551-worker|oc551-edge')
    srv, path = make_server(container)
    print(f'fill route (single use): http://127.0.0.1:{srv.server_address[1]}{path}', flush=True)
    serve(srv, float(os.environ.get('FILL_TIMEOUT', '600')), hard_exit=True)
    print('fill route closed', flush=True)


if __name__ == '__main__':
    main()
