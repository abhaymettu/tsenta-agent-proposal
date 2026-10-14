"""core/worker.py with a fake command runner: no Docker, no model, no OpenClaw (551 v33 MUSTs)."""
import json, pathlib, subprocess, threading, time, unittest
from core.worker import TurnUnknown, Worker, WorkerOffline, safe_argv

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Fake:
    def __init__(self, out, rc=0, write_rc=0):
        self.calls, self.out, self.rc, self.write_rc = [], out, rc, write_rc

    def __call__(self, argv, input=None, capture_output=True, timeout=None):
        self.calls.append((argv, input))
        if argv[-1].startswith('umask'):
            return subprocess.CompletedProcess(argv, self.write_rc, b'', b'')
        return subprocess.CompletedProcess(argv, self.rc, self.out.encode(), b'')


OK = json.dumps({'runId': 'r1', 'status': 'ok',
                 'result': {'payloads': [{'text': 'two applications are open'}], 'meta': {'agentMeta': {'model': 'm'}}}})


class WorkerTurn(unittest.TestCase):
    def test_task_goes_over_stdin_and_the_turn_is_the_fixed_command(self):
        f = Fake(OK)
        out = Worker(container='oc551-worker', run=f).run_turn('tsenta-demo-g0-P01', 'what is open?', 't1')
        (write, task), (turn, none) = f.calls
        self.assertEqual(task, b'what is open?')
        self.assertNotIn('what is open?', ' '.join(write + turn), 'the task text never goes in argv')
        self.assertEqual(write[-1], 'umask 077; cat > /demo/io/task.md')
        self.assertEqual(turn[-2:], ['/opt/demo/agent-turn.sh', 'tsenta-demo-g0-P01'])
        self.assertIsNone(none)
        self.assertEqual((out['reply'], out['run_id'], out['model']), ('two applications are open', 'r1', 'm'))
        gw = Worker(container='oc551-worker', run=Fake(OK.replace('"status"', '"origin": "gateway", "status"'))).run_turn('tsenta-demo-g0-P01', 'x', 't')
        self.assertEqual(gw['run_id'], 'r1', 'origin "gateway" is still accepted')

    def test_fails_closed(self):
        cases = {'not gateway': Fake(OK.replace('"status"', '"origin": "local", "status"')),
                 'origin null': Fake(OK.replace('"status"', '"origin": null, "status"')),
                 'no runId': Fake(OK.replace('"r1"', '""')), 'no result': Fake(json.dumps({'runId': 'r1', 'status': 'ok'})),
                 'not json': Fake('Gateway agent call failed'), 'error status': Fake(OK.replace('"ok"', '"error"')),
                 'exit 1': Fake(OK, rc=1), 'key-shaped': Fake(OK.replace('two applications', 'sk-ant-xyz')),
                 'write failed': Fake(OK, write_rc=1)}
        for name, f in cases.items():
            with self.subTest(name), self.assertRaises(WorkerOffline):
                Worker(container='oc551-worker', run=f).run_turn('tsenta-demo-g0-P01', 'x', 't')
        with self.assertRaises(WorkerOffline):
            Worker(container='oc551-worker', run=Fake(OK)).run_turn('a; rm -rf /', 'x', 't')
        with self.assertRaises(WorkerOffline):
            Worker(container=None, run=Fake(OK)).run_turn('tsenta-demo-g0-P01', 'x', 't')

    def test_turns_are_serialized(self):
        order, lock = [], threading.Lock()
        def run(argv, input=None, capture_output=True, timeout=None):
            with lock: order.append(('write', input) if argv[-1].startswith('umask') else ('turn', None))
            time.sleep(0.05)
            return subprocess.CompletedProcess(argv, 0, OK.encode() if not argv[-1].startswith('umask') else b'', b'')
        w = Worker(container='oc551-worker', run=run)
        ts = [threading.Thread(target=w.run_turn, args=('tsenta-demo-g0-P01', t, 'x')) for t in ('A', 'B')]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual([k for k, _ in order], ['write', 'turn', 'write', 'turn'], 'each write is followed by its own turn')

    def test_timeouts(self):
        def turn_times_out(argv, input=None, capture_output=True, timeout=None):
            if argv[-1].startswith('umask'):
                return subprocess.CompletedProcess(argv, 0, b'', b'')
            raise subprocess.TimeoutExpired(argv, timeout)
        with self.assertRaises(TurnUnknown) as c:
            Worker(container='oc551-worker', run=turn_times_out).run_turn('tsenta-demo-g0-P01', 'x', 't')
        self.assertIn('UNKNOWN', str(c.exception))
        def write_fails(argv, input=None, capture_output=True, timeout=None):
            raise OSError('docker missing')
        with self.assertRaises(WorkerOffline) as c:
            Worker(container='oc551-worker', run=write_fails).run_turn('tsenta-demo-g0-P01', 'x', 't')
        self.assertNotIsInstance(c.exception, TurnUnknown, 'a failed write means no turn started')

    def test_never_local_and_never_agent_exec(self):
        for argv in (['openclaw', 'agent', '--local'], ['openclaw', 'agent', 'exec', 'x']):
            with self.assertRaises(WorkerOffline):
                safe_argv(argv)
        script = (ROOT / 'openclaw' / 'agent-turn.sh').read_text()
        cmd = [l for l in script.splitlines() if l.startswith('exec openclaw')]
        self.assertEqual(len(cmd), 1)
        self.assertNotIn('--local', script)
        self.assertNotIn('agent exec', script)
        self.assertIn('--message-file /demo/io/task.md', cmd[0])


if __name__ == '__main__':
    unittest.main()
