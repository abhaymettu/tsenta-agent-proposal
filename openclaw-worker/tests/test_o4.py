"""O4 receipt offline (569 section 4): a real core serving over HTTP, restarted on the same run dir after 22 steps, with
docker and lsof stubbed. Proves the comparisons, the lowercased key match, the compaction UNKNOWN and the FAIL paths.
No Docker, no model."""
import copy, io, json, os, sys, threading, unittest
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'openclaw')]
import o4_receipt as o4
import run_prompts as rp
from server.serve import handler
from tests.test_restart_reset import restart
from tests.test_run_prompts import PLAN, P23


def serve(app):
    s = ThreadingHTTPServer(('127.0.0.1', 0), handler(app))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f'http://127.0.0.1:{s.server_address[1]}'


class Docker:
    """Stub for docker inspect/top/exec and lsof: fixed containers and gateway, a settable core pid and session row."""
    def __init__(self):
        self.pid, self.rows = '100', None

    def __call__(self, argv):
        if argv[0] == 'lsof':
            return self.pid + '\n'
        if 'inspect' in argv:
            return '/oc551-worker w1 2026-10-14T01:50:53Z true\n/oc551-edge e1 2026-10-13T21:27:00Z true\n'
        if 'top' in argv:
            return 'PID COMMAND\n16181 node openclaw gateway --port 18789\n'
        if 'sessions' in argv:
            return self.rows


class O4(unittest.TestCase):
    def setUp(self):
        self.route = rp.InProcess(PLAN)
        self.assertEqual(rp.run(self.route, rp.load(P23, 1, 22), io.StringIO(), 0, settle=0)['result'], 'PASS')
        self.log = os.path.join(self.route.dir, 'core.log')
        self.dock = Docker()
        self.key = self.route.app.session_key()   # tsenta-demo-g1-P01; OpenClaw stores it lowercased
        self.row = {'key': 'agent:main:' + self.key.lower(), 'sessionId': 's-1', 'sessionStartedAt': 1, 'totalTokens': 50000}
        self.dock.rows = '{"sessions": [%s]}' % json_row(self.row)

    def cap(self, app):
        srv, base = serve(app)
        try:
            return o4.capture(base, self.route.dir, self.log, 'P01', sh=self.dock)
        finally:
            srv.shutdown()

    def boot(self, line='token pushed: yes'):
        with open(self.log, 'w') as f:
            f.write(f'serving on 127.0.0.1:8550\n{line}\n')

    def test_core_restart_then_a_turn_passes(self):
        self.boot()
        pre = self.cap(self.route.app)
        self.assertEqual((len(pre['thread']), pre['session']['sessionId'], pre['active_turn']), (44, 's-1', False))
        b = restart(self.route)   # a new process on the same core.db, sandbox.db and thread.db
        self.dock.pid = '200'
        post = self.cap(b)
        self.assertEqual(o4.result(o4.compare(pre, post), turn=False), 'PARTIAL', o4.compare(pre, post))   # never PASS
        self.route.app, self.route.step = b, 23
        b.message(rp.load(P23, 23, 23)[0]['prompt'])
        self.dock.rows = '{"sessions": [%s]}' % json_row(dict(self.row, totalTokens=52000))
        turn = self.cap(b)
        self.assertEqual(o4.result(o4.compare(pre, post, turn)), 'PASS', o4.compare(pre, post, turn))

        # compaction: a smaller context is UNKNOWN, never a FAIL on its own
        self.dock.rows = '{"sessions": [%s]}' % json_row(dict(self.row, totalTokens=9000))
        checks = o4.compare(pre, post, self.cap(b))
        self.assertEqual(o4.result(checks), 'UNKNOWN')
        self.assertTrue(any('possible compaction' in n and ok is None for n, ok in checks))
        # a stale token snapshot makes the weak check UNKNOWN (551 v112)
        self.dock.rows = '{"sessions": [%s]}' % json_row(dict(self.row, totalTokens=52000, totalTokensFresh=False))
        self.assertIn(('totalTokens fresh (totalTokensFresh false: a stale snapshot)', None), o4.compare(pre, post, self.cap(b)))
        # a new sessionId is a FAIL (the agent lost its context)
        self.dock.rows = '{"sessions": [%s]}' % json_row(dict(self.row, sessionId='s-2', totalTokens=900))
        self.assertEqual(o4.result(o4.compare(pre, post, self.cap(b))), 'FAIL')

    def test_fail_and_unknown_paths(self):
        self.boot()
        pre = self.cap(self.route.app)
        b = restart(self.route)
        post = self.cap(b)   # same pid: no restart happened
        self.assertIn(('a new core pid', False), o4.compare(pre, post))
        self.dock.pid = '200'
        for change, name in (({'gateway_pid': '99'}, 'gateway pid unchanged'),
                             ({'containers': 'other'}, 'worker and edge Id/StartedAt unchanged'),
                             ({'generation': pre['generation'] + 1}, 'generation served unchanged'),
                             ({'receipts': ['x'] + pre['receipts'][1:]}, 'receipts.jsonl keeps its prefix'),
                             ({'session': {}}, 'OpenClaw session row present before and after'),
                             ({'token_pushed': 'no'}, 'the new boot printed "token pushed: yes"')):
            p2 = dict(copy.deepcopy(self.cap(b)), **change)
            self.assertIn((name, False), o4.compare(pre, p2), name)
        self.assertEqual(o4.result(o4.compare(pre, dict(self.cap(b), session=None))), 'UNKNOWN')
        idle, done = 'before: no active turn (active_turn false, not missing)', 'before: the last receipt is complete (a run id, no worker state)'
        for active in (True, None):
            self.assertIn((idle, False), o4.compare(dict(pre, active_turn=active), self.cap(b)), active)
        for last in (None, {}, {'run_id': None, 'state': None}, {'run_id': 'r', 'state': 'unknown'},
                     {'run_id': 'r', 'state': 'offline'}, {'run_id': ''}, {'run_id': 'r'}):   # O4SOURCE0142: missing is not complete
            self.assertIn((done, False), o4.compare(dict(pre, last_receipt=last), self.cap(b)), last)
        self.assertIn((done, True), o4.compare(pre, self.cap(b)))
        # a row with empty identity fields is UNKNOWN, never "unchanged" (None == None)
        empty = {'key': 'agent:main:x', 'sessionId': None, 'sessionStartedAt': None, 'totalTokens': None, 'totalTokensFresh': None}
        checks = o4.compare(dict(pre, session=empty), dict(self.cap(b), session=empty))
        self.assertEqual(o4.result(checks), 'UNKNOWN')
        self.assertIn(('sessionId and sessionStartedAt non-empty before and after', None), checks)
        turn = dict(self.cap(b), session=dict(pre['session'], sessionId=''))
        self.assertIn(('sessionId and sessionStartedAt non-empty after the turn', None), o4.compare(pre, self.cap(b), turn))

    def test_sessions_command_is_guarded(self):
        # 551 v114: exactly the traced read, with its side effects switched off and an in-container timeout
        self.assertEqual(o4.SESSIONS, ['docker', '--context', 'desktop-linux', 'exec', '-u', 'node', '-e', 'OPENCLAW_NO_RESPAWN=1',
                                       '-e', 'NODE_DISABLE_COMPILE_CACHE=1', '-e', 'OPENCLAW_LOG_LEVEL=silent', 'oc551-worker',
                                       'timeout', '30', 'openclaw', 'sessions', '--agent', 'main', '--json'])

    def test_session_row_parsing(self):
        row = json_row(self.row)
        self.assertEqual(o4.session_row('[%s]' % row, self.key)['sessionId'], 's-1')   # P01 matches the stored p01
        self.assertEqual(o4.session_row('{"rows": [%s]}' % row, self.key.upper())['sessionId'], 's-1')
        # an absent target: only hasMore exactly false is a complete listing ({} -> FAIL); anything else UNKNOWN (SOURCE0158)
        other = 'tsenta-demo-g9-P01'
        self.assertEqual(o4.session_row('{"hasMore": false, "sessions": [%s]}' % row, other), {})
        for listing in ('{"hasMore": true, "sessions": [%s]}', '{"sessions": [%s]}', '{"hasMore": null, "sessions": [%s]}',
                        '{"hasMore": "false", "sessions": [%s]}', '{"hasMore": 0, "sessions": [%s]}', '[%s]'):
            self.assertIsNone(o4.session_row(listing % row, other), listing)
        for bad in (None, 'not json', '{"x": 1}', '[{"key": "sk-ant-x"}]'):
            self.assertIsNone(o4.session_row(bad, self.key), bad)


def json_row(r):
    return json.dumps(r)


if __name__ == '__main__':
    unittest.main()
