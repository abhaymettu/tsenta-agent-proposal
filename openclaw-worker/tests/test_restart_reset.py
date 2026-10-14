"""G8 and G9 offline (548 s9, spec 004 order 4-5): after the 24-prompt run's first 22 steps, a core-only restart keeps the
thread, record, preference, generation and session key; /api/reset then clears them and rotates the generation and the
session key; a second restart keeps the reset state. Real core, sandbox and server App on a temp dir; no Docker, no model."""
import io, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'openclaw')]
import run_prompts as rp
from core.engine import Core
from core.sandbox import Sandbox
from server.serve import App
from tests.test_run_prompts import PLAN, P23

BASE = {'pending': None, 'resumes': {'R011': 2, 'R012': 1, 'R013': 1}, 'submitted': 0, 'outbox': 0, 'outbox_to': [],
        'drafts': 0, 'preferences': 0}


def restart(route):
    """What a core-only restart does: a new process opens the same core.db, sandbox.db and thread.db."""
    core = Core(os.path.join(ROOT, 'fixtures', 'seed.json'), Sandbox(os.path.join(route.dir, 'sandbox.db')),
                db=os.path.join(route.dir, 'core.db'))
    app = App(core, rp.ScriptedWorker(PLAN), route.dir)
    app.worker.app, app.worker.route = app, route
    app.push_token = lambda: True
    return app


class RestartReset(unittest.TestCase):
    def test_restart_keeps_then_reset_clears(self):
        route = rp.InProcess(PLAN)
        res = rp.run(route, rp.load(P23, 1, 22), io.StringIO(), 0, settle=0)
        self.assertEqual(res['result'], 'PASS')
        a = route.app
        before = dict(thread=a.thread(), gen=a.core.gen, key=a.session_key(), state=rp.state(route.dir, 'P01'))
        self.assertEqual(len(before['thread']), 44)   # 22 typed messages and 22 replies
        self.assertEqual({k: before['state'][k] for k in ('submitted', 'outbox', 'preferences')},
                         {'submitted': 1, 'outbox': 1, 'preferences': 1})

        b = restart(route)   # G8: core-only restart
        self.assertEqual(b.thread(), before['thread'])
        last = b.last_receipt()   # G10: a reload shows the last turn's receipt, not "No turn yet"
        self.assertEqual((last['gen'], last['persona']), (before['gen'], 'P01'))
        self.assertEqual([e['tool'] for e in last['tools']], ['save_preference'])
        with open(os.path.join(route.dir, 'receipts.jsonl'), 'a') as f:
            f.write('{not json\n')   # a damaged line is skipped, not raised
        self.assertEqual(b.last_receipt()['turn'], last['turn'])
        b.switch('P02')   # another persona with no turn yet sees no receipt, never P01's
        self.assertIsNone(b.last_receipt())
        b.switch('P01')
        self.assertEqual(b.last_receipt()['turn'], last['turn'])
        self.assertEqual((b.core.gen, b.session_key()), (before['gen'], before['key']))
        self.assertEqual(rp.state(route.dir, 'P01'), before['state'])
        self.assertNotEqual(b.token, a.token)   # a new boot mints a new MCP bearer (memory only)
        self.assertIn('remote', ' '.join(p['text'] for p in b.core.s['preferences'] if p['persona_id'] == 'P01'))

        b.reset()   # G9
        self.assertEqual(b.core.gen, before['gen'] + 1)
        self.assertEqual(b.session_key(), f"tsenta-demo-g{before['gen'] + 1}-P01")
        self.assertEqual(b.thread(), [])
        self.assertIsNone(b.last_receipt())   # older generations' receipts are not shown
        self.assertEqual(rp.state(route.dir, 'P01'), BASE)

        c = restart(route)   # the reset state survives a further restart
        self.assertEqual((c.core.gen, c.session_key(), c.thread()), (b.core.gen, b.session_key(), []))
        self.assertEqual(rp.state(route.dir, 'P01'), BASE)


if __name__ == '__main__':
    unittest.main()
