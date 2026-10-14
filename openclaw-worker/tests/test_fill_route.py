"""openclaw/fill-route.py: exact bytes to the fill once; every malformed or foreign request never reaches the fill."""
import importlib.util, json, os, shutil, socket, sys, tempfile, threading, time, unittest

spec = importlib.util.spec_from_file_location('fill_route', os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'fill-route.py'))
fill_route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fill_route)
FAKE = b'fake-value-123'


class FillRoute(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.calls = os.path.join(self.dir, 'calls')
        # stands in for fill-key.sh: appends one line per invocation (never the value) and succeeds only on the fake value
        check = [sys.executable, '-c', f"import sys; open({self.calls!r}, 'a').write('call\\n'); sys.exit(0 if sys.stdin.buffer.read() == {FAKE + fill_route.FRAME_END!r} else 3)"]
        self.srv, self.path = fill_route.make_server('oc551-worker', check, read_timeout=0.5)
        self.host = f'127.0.0.1:{self.srv.server_address[1]}'
        self.t = threading.Thread(target=fill_route.serve, args=(self.srv, 5), daemon=True)
        self.t.start()

    def tearDown(self):
        self.srv.shutdown()
        self.t.join(5)
        shutil.rmtree(self.dir, ignore_errors=True)

    def fills(self):
        if not os.path.exists(self.calls):
            return 0
        with open(self.calls) as f:
            return f.read().count('call')

    def raw(self, method, path=None, body=b'', host=None, origin='own', ctype='text/plain', length=None, send_body=None, hold=0, chunked=False):
        """One request over a plain socket, so tests can send headers no HTTP client would (bad lengths, partial bodies)."""
        h = [f'{method} {path or self.path} HTTP/1.1', f'Host: {host or self.host}']
        if origin:
            h.append('Origin: ' + ('http://' + self.host if origin == 'own' else origin))
        if method == 'POST':
            h += [f'Content-Type: {ctype}', f'Content-Length: {len(body) if length is None else length}']
            if chunked:
                h.append('Transfer-Encoding: chunked')
        try:
            s = socket.create_connection(self.srv.server_address, timeout=5)
        except OSError:
            return 'closed', None
        with s:
            s.sendall(('\r\n'.join(h) + '\r\n\r\n').encode() + (body if send_body is None else send_body))
            if hold:
                time.sleep(hold)
            data = b''
            try:
                while chunk := s.recv(65536):
                    data += chunk
            except OSError:
                pass
        if not data:
            return 'closed', None
        head, _, payload = data.partition(b'\r\n\r\n')
        return int(head.split()[1]), payload

    def test_page_and_success_once(self):
        code, page = self.raw('GET')
        self.assertEqual(code, 200)
        self.assertIn(b'type="password"', page)
        self.assertIn(b'autocomplete="off"', page)  # 551 U1: the browser must not offer to save the key
        self.assertNotIn(b'current-password', page)
        code, body = self.raw('POST', body=b'  ' + FAKE + b'\n')
        self.assertEqual((code, json.loads(body)), (200, {'filled': 'yes'}))
        self.assertEqual(self.fills(), 1)
        self.t.join(5)
        self.assertFalse(self.t.is_alive(), 'the route closes after one fill')
        self.assertEqual(self.raw('POST', body=FAKE)[0], 'closed', 'a second fill finds nothing listening')
        self.assertEqual(self.fills(), 1)

    def test_foreign_or_malformed_requests_never_fill(self):
        cases = [dict(path='/fill/wrong'), dict(host='evil.example:80'), dict(host='localhost:%d' % self.srv.server_address[1]),
                 dict(origin=None), dict(origin='http://evil.example'), dict(origin='null'),
                 dict(ctype='application/x-www-form-urlencoded'), dict(length='abc'), dict(length='-5'), dict(length=10 ** 6),
                 dict(length=''), dict(chunked=True)]
        for c in cases:
            with self.subTest(**c):
                self.assertIn(self.raw('POST', body=FAKE, **c)[0], (400, 404))
        self.assertEqual(self.raw('GET', host='evil.example:80')[0], 404)
        self.assertEqual(self.fills(), 0)
        self.assertEqual(json.loads(self.raw('POST', body=FAKE)[1]), {'filled': 'yes'}, 'none of those consumed the route')

    def test_partial_body_never_fills_and_closes(self):
        code, body = self.raw('POST', body=FAKE, length=len(FAKE) + 10, hold=1.0)  # declares more than it sends, then waits
        self.assertEqual((code, json.loads(body)), (200, {'filled': 'no'}))
        self.assertEqual(self.fills(), 0)
        self.t.join(5)
        self.assertFalse(self.t.is_alive())

    def test_multiline_value_never_fills(self):
        code, body = self.raw('POST', body=FAKE + b'\nOC551-END\nmore')  # cannot smuggle its own frame
        self.assertEqual((code, json.loads(body)), (200, {'filled': 'no'}))
        self.assertEqual(self.fills(), 0)

    def test_empty_value_never_fills(self):
        code, body = self.raw('POST', body=b'   \n')
        self.assertEqual((code, json.loads(body)), (200, {'filled': 'no'}))
        self.assertEqual(self.fills(), 0)

    def test_concurrent_posts_fill_once(self):
        results = []
        ts = [threading.Thread(target=lambda: results.append(self.raw('POST', body=FAKE)[0])) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(10)
        self.assertEqual(self.fills(), 1)
        self.assertEqual(results.count(200), 1, results)
        self.assertTrue(all(r in (200, 404, 'closed') for r in results), results)


class IdleTimeout(unittest.TestCase):
    def test_idle_route_closes_without_filling(self):
        srv, _ = fill_route.make_server('oc551-worker', [sys.executable, '-c', 'raise SystemExit(9)'])
        t = threading.Thread(target=fill_route.serve, args=(srv, 0.3), daemon=True)
        t.start()
        t.join(5)
        self.assertFalse(t.is_alive())
        with self.assertRaises(OSError):
            socket.create_connection(srv.server_address, timeout=1).close()


if __name__ == '__main__':
    unittest.main()


BROWSER = os.environ.get('FILL_BROWSER', os.path.join(os.environ.get('TSENTA_AUDIT_DIR', 'run/audit'), 'bin', 'fill-browser'))


@unittest.skipUnless(os.path.exists(BROWSER), f'offscreen fill-browser not built (swiftc -O openclaw/fill-browser.swift -o {BROWSER})')
class RealBrowser(unittest.TestCase):
    def test_webkit_page_fills_once_with_its_own_origin_and_csp(self):
        import re, subprocess
        d = tempfile.mkdtemp()
        calls = os.path.join(d, 'calls')
        # accepts only the page-generated canary shape; records the call, never the value
        check = [sys.executable, '-c', "import re, sys; v = sys.stdin.buffer.read(); open(%r, 'a').write('call\\n'); "
                 "sys.exit(0 if re.fullmatch(rb'sk-ant-canary-[0-9a-f]{48}\\nOC551-END\\n', v) else 3)" % calls]
        srv, path = fill_route.make_server('oc551-worker', check)
        t = threading.Thread(target=fill_route.serve, args=(srv, 30), daemon=True)
        t.start()
        out = subprocess.run([BROWSER, f'http://127.0.0.1:{srv.server_address[1]}{path}'], capture_output=True, text=True, timeout=60)
        t.join(5)
        self.assertEqual(out.stdout.split(), ['filled:', 'yes', 'dom-inputs:', '0'])
        self.assertNotRegex(out.stdout + out.stderr, r'sk-ant-canary-[0-9a-f]', 'the tool never prints the value')
        with open(calls) as f:
            self.assertEqual(f.read().count('call'), 1)
        self.assertFalse(t.is_alive())
        shutil.rmtree(d, ignore_errors=True)


class FrameCheck(unittest.TestCase):
    """The frame check fill-key.sh runs inside the container, run here on the host's sh with a scratch dir (coreutils
    tail/truncate/stat semantics are the same). A truncated stream is refused (exit 8) and nothing is published."""
    SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'openclaw', 'fill-key.sh')

    def frame_part(self):
        with open(self.SCRIPT) as f:
            s = f.read()
        i, j = s.index('    n=$(stat -c %s "$P")'), s.index('    [ -s "$P" ] || exit 5')
        return s[i:j]

    def run_frame(self, data):
        import subprocess
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'part')
        with open(p, 'wb') as f:
            f.write(data)
        stat = 'stat -f %z' if sys.platform == 'darwin' else 'stat -c %s'
        trunc = 'truncate -s' if subprocess.run(['sh', '-c', 'command -v truncate'], capture_output=True).returncode == 0 else None
        body = self.frame_part().replace('stat -c %s', stat)
        if not trunc:  # macOS without coreutils: same effect, for the test only
            body = body.replace('truncate -s $((n - 11)) "$P"', 'python3 -c "import os,sys; os.truncate(sys.argv[1], int(sys.argv[2]))" "$P" $((n - 11))')
        r = subprocess.run(['sh', '-c', 'set -eu; P="$1"\n' + body, 'sh', p], capture_output=True)
        with open(p, 'rb') as f:
            out = f.read()
        shutil.rmtree(d, ignore_errors=True)
        return r.returncode, out

    def test_complete_frame_is_stripped(self):
        self.assertEqual(self.run_frame(FAKE + fill_route.FRAME_END), (0, FAKE))

    def test_truncated_stream_is_refused(self):
        for cut in (FAKE, FAKE + b'\nOC551-EN', FAKE + b'\nOC551-END', b'x' * 40):
            with self.subTest(cut=cut):
                self.assertEqual(self.run_frame(cut)[0], 8)
