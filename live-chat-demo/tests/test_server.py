# Run: python3 -m unittest discover tests
import importlib.util, json, os, pathlib, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import serve  # noqa: E402


def stop(w):
    """End a worker the way the server's own exit does: close its stdin (node exits at EOF), then reap it."""
    if w.p is not None:
        w.p.stdin.close()
        w.p.wait(timeout=5)
        w.p.stdout.close()
        w.p = None


def tearDownModule():
    stop(serve.WORKER)



class MockReply(unittest.TestCase):
    def test_word_match_not_substring(self):
        self.assertEqual(serve.mock_reply("yesterday?"), serve.MOCK_DEFAULT)
        self.assertIn("one exact thing", serve.mock_reply("Yes"))

    def test_action_words_claim_no_action(self):
        # Mock mode never changes state, so a canned reply must not say it paused, sent or undid anything.
        for text in ("pause", "undo", "yes", "apply now"):
            self.assertIn("nothing", serve.mock_reply(text).lower(), text)

    def test_first_match_wins(self):
        self.assertIn("interview", serve.mock_reply("can you send my interview times"))


class LiveConfig(unittest.TestCase):
    def test_default_model_is_fast_and_priced(self):
        self.assertIn(serve.MODEL, ("claude-haiku-5-5", "claude-sonnet-5-5"))
        self.assertEqual(serve.PRICES["claude-haiku-5-5"], (0.10, 0.50))
        self.assertEqual(serve.PRICES["claude-sonnet-5-5"], (2.00, 10.00))

    def test_schema_matches_intent_contract(self):
        js = pathlib.Path(ROOT, "intents.js").read_text()
        for t in serve.INTENT_TYPES:
            self.assertIn(f"{t}", js, t)
        intent = serve.SCHEMA["properties"]["intent"]
        self.assertEqual(sorted(intent["required"]), sorted(["type"] + list(serve.INTENT_FIELDS)))


class Ledger(unittest.TestCase):
    """Spend ledger (adversarial review finding 9): priced before the call, never reset by a bad read, written under the lock."""

    def setUp(self):
        import tempfile, types
        self.tmp = tempfile.mkdtemp()
        self.saved = (serve.HERE, serve.SPEND_FILE, serve.keychain_key, serve.call_api, sys.modules.get("anthropic"))
        serve.HERE, serve.SPEND_FILE = self.tmp, os.path.join(self.tmp, "spend.json")
        pathlib.Path(self.tmp, "live.json").write_text(json.dumps({"balance_verified": "test"}))
        serve.keychain_key = lambda: "test-key"
        serve._client = None  # built from the stubbed SDK below
        self.clients = []
        sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=lambda **kw: self.clients.append(kw) or object(), Timeout=lambda **kw: kw)
        self.calls = 0

        self.timeouts = []

        def fake_api(client, model, context, extra, text, timeout):
            self.calls += 1
            self.timeouts.append(timeout)
            block = types.SimpleNamespace(type="text", text=json.dumps({"intent": {"type": "answer", "topic": "unclear"}}))
            return types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=1000, output_tokens=100), stop_reason="end_turn", content=[block], model=model)
        serve.call_api = fake_api

    def tearDown(self):
        serve.HERE, serve.SPEND_FILE, serve.keychain_key, serve.call_api, mod = self.saved
        serve._client = None
        if mod is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = mod

    def test_records_spend_atomically(self):
        out = serve.call_claude({"userText": "hi"}, model="claude-haiku-5-5")
        self.assertEqual(out["mode"], "live")
        led = json.loads(pathlib.Path(serve.SPEND_FILE).read_text())
        self.assertAlmostEqual(led["usd"], (1000 * 0.10 + 100 * 0.50) / 1e6)
        self.assertEqual(led["calls"], 1)
        self.assertFalse(os.path.exists(serve.SPEND_FILE + ".tmp"))

    def test_one_client_per_process(self):
        serve.call_claude({"userText": "hi"}, model="claude-haiku-5-5")
        serve.call_claude({"userText": "again"}, model="claude-haiku-5-5")
        self.assertEqual(self.calls, 2)
        self.assertEqual(len(self.clients), 1, "the second request reuses the client (and its connection)")
        self.assertEqual(self.clients[0]["max_retries"], 0)

    def test_unpriced_model_fails_before_any_call(self):
        with self.assertRaises(ValueError):
            serve.call_claude({"userText": "hi"}, model="claude-unknown-9")
        self.assertEqual(self.calls, 0)

    def test_no_money_cap(self):
        pathlib.Path(serve.SPEND_FILE).write_text(json.dumps({"usd": 50.0, "calls": 9}))
        pathlib.Path(self.tmp, "live.json").write_text(json.dumps({"balance_verified": "test", "cap_usd": 0.5}))  # an old file's cap is ignored
        self.assertEqual(serve.call_claude({"userText": "hi"}, model="claude-haiku-5-5")["mode"], "live")
        self.assertEqual(self.calls, 1)
        self.assertEqual(json.loads(pathlib.Path(serve.SPEND_FILE).read_text())["calls"], 10, "spend is still recorded")

    def test_unreadable_ledger_is_an_error_not_zero(self):
        pathlib.Path(serve.SPEND_FILE).write_text('{"usd": 0.4')
        with self.assertRaises(ValueError):
            serve.call_claude({"userText": "hi"}, model="claude-haiku-5-5")
        self.assertEqual(self.calls, 0)
        self.assertEqual(pathlib.Path(serve.SPEND_FILE).read_text(), '{"usd": 0.4', "never overwritten")
        self.assertEqual(serve.status().get("reason"), "spend ledger unreadable")


class Budget(unittest.TestCase):
    """A request ends on the server before the browser gives up on it (verification nit, 10:59 operator)."""

    def test_phases_and_lock_wait_fit_inside_the_browser_abort(self):
        import types, re
        saved = sys.modules.get("anthropic")
        sys.modules["anthropic"] = types.SimpleNamespace(Timeout=lambda **kw: kw)  # the SDK's own Timeout (anthropic 1.13)
        try:
            t = serve.call_timeout(serve.BUDGET_S)
        finally:
            sys.modules.pop("anthropic", None) if saved is None else sys.modules.__setitem__("anthropic", saved)
        self.assertLessEqual(sum(t.values()), serve.BUDGET_S, "every phase of the call together")
        app = pathlib.Path(ROOT, "app.js").read_text()
        self.assertEqual(int(re.search(r"AbortSignal\.timeout\((\d+)\)", app).group(1)) / 1000, serve.BROWSER_ABORT_S)
        self.assertLess(serve.BUDGET_S, serve.BROWSER_ABORT_S, "lock wait is inside the budget: it is measured from the start")


class Backend(unittest.TestCase):
    """The demo backend for real: SQLite file, node worker, the same rules as the browser. No network, no model."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.saved = (serve.DB_FILE, serve.status, serve.call_claude)
        serve.DB_FILE = os.path.join(self.tmp, "demo.db")
        self.intents = []  # what the stub model proposes next, in order
        serve.status = lambda: {"mode": "live", "model": "stub"}
        serve.call_claude = self.fake_claude
        con = serve.db(); serve.reset(con); con.close()

    def tearDown(self):
        serve.DB_FILE, serve.status, serve.call_claude = self.saved

    def fake_claude(self, req, t0=None):
        nxt = self.intents.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return {"mode": "live", "intent": nxt, "model": "claude-stub"}

    def send(self, text, key, seen=None):
        if seen is None:
            seen = self.thread()["seen"]
        code, resp = serve.handle_message({"text": text, "key": key, "seen": seen})
        self.assertEqual(code, 200)
        return resp

    def thread(self):
        con = serve.db()
        try:
            return serve.thread(con)
        finally:
            con.close()

    def test_state_and_thread_survive_a_restart(self):
        r = self.send("ok resume", "k1")
        self.assertFalse(r["state"]["paused"])
        self.assertEqual(r["messages"][1]["tag"], "reply written by code · no model call")
        before = self.thread()
        con = serve.db(); serve.rebuild(con); con.close()  # what start-up does: replay the event log
        after = self.thread()
        self.assertEqual(after["state"], before["state"], "state rebuilt from the event log equals the cached state")
        self.assertEqual([m["text"] for m in after["messages"]], [m["text"] for m in before["messages"]])
        self.assertEqual(after["events"], 37, "36 seed events plus resumed")

    def test_the_same_send_twice_is_answered_once(self):
        a = self.send("ok resume", "same")
        b = self.send("ok resume", "same")
        self.assertEqual(a, b)
        t = self.thread()
        self.assertEqual([m["who"] for m in t["messages"]], ["me", "them", "sys"])
        self.assertEqual(t["events"], 37)

    def test_a_yes_answers_the_question_only_if_she_saw_it_last(self):
        self.send("ok resume", "k1")
        seen_before_question = self.thread()["seen"]
        self.intents.append({"type": "pause"})
        ask = self.send("could you hold off on everything?", "k2")
        self.assertTrue(ask["messages"][1]["text"].startswith("Pause Tsenta?"))
        self.intents.append({"type": "answer", "topic": "unclear"})
        late = self.send("yes", "k3", seen=seen_before_question)  # typed before the question reached her screen
        self.assertFalse(late["state"]["paused"])
        self.intents.append({"type": "pause"})
        self.send("could you hold off on everything?", "k4")
        yes = self.send("yes", "k5")
        self.assertTrue(yes["state"]["paused"])
        self.assertEqual(yes["messages"][1]["tag"], "reply written by code · no model call")

    def test_a_failed_model_call_changes_nothing_and_drops_the_open_question(self):
        self.send("ok resume", "k1")
        self.intents.append({"type": "pause"})
        self.send("could you hold off on everything?", "k2")
        self.intents.append(TimeoutError("slow"))
        err = self.send("also, anything from corvid?", "k3")
        self.assertEqual(err["messages"][1]["tag"], "live error")
        self.intents.append({"type": "answer", "topic": "unclear"})
        yes = self.send("yes", "k4")
        self.assertFalse(yes["state"]["paused"], "the error message came after the question")

    def test_without_claude_code_still_answers_what_it_can(self):
        serve.status = lambda: {"mode": "mock", "reason": "no key in Keychain"}
        self.assertTrue(self.send("status", "k1")["messages"][1]["text"].startswith("6 applied, "))
        held = self.send("who is Priya?", "k2")
        self.assertEqual(held["messages"][1]["text"], serve.HELD)
        self.assertTrue(held["messages"][1]["tag"].startswith("Claude not connected"))

    def test_reset_returns_to_the_seed(self):
        self.send("ok resume", "k1")
        con = serve.db(); serve.reset(con); con.close()
        t = self.thread()
        self.assertEqual((t["messages"], t["events"], t["state"]["paused"]), ([], 36, True))

    def test_a_yes_from_before_a_reset_never_answers_a_question_after_it(self):
        """Review 11:27, finding 1: a stale tab's count can equal the fresh thread's count after a reset."""
        self.send("status", "k1")
        stale = self.thread()["seen"]  # tab 2: one agent message on screen
        con = serve.db(); serve.reset(con); con.close()  # tab 1 resets
        self.intents.append({"type": "resume"})
        ask = self.send("can you start again?", "k2")  # tab 1: one agent message again, a yes question
        self.assertTrue(ask["messages"][1]["text"].startswith("Resume Tsenta?"))
        self.assertNotEqual(stale, ask["seen"])
        self.intents.append({"type": "answer", "topic": "unclear"})
        late = self.send("yes", "k3", seen=stale)
        self.assertTrue(late["state"]["paused"], "tab 2 never saw the question")

    def test_waiting_for_the_lock_is_inside_the_budget(self):
        """Review finding 2: a message that waited for another one gets only what is left of the 22 s."""
        import threading, time as t
        budgets = []
        real = serve.call_claude
        serve.call_claude = lambda req, t0=None: budgets.append(serve.BUDGET_S - (t.monotonic() - t0)) or {"mode": "live", "intent": {"type": "answer", "topic": "unclear"}, "model": "claude-stub"}
        try:
            serve.TURN_LOCK.acquire()
            threading.Timer(0.5, serve.TURN_LOCK.release).start()
            self.send("anything from corvid?", "k1")
        finally:
            serve.call_claude = real
        self.assertLess(budgets[0], serve.BUDGET_S - 0.4)

    def test_a_busy_lock_past_the_budget_stores_nothing(self):
        saved = serve.BUDGET_S
        serve.BUDGET_S = 7.3  # lock timeout 0.3 s
        serve.TURN_LOCK.acquire()
        try:
            code, resp = serve.handle_message({"text": "status", "key": "k1", "seen": self.thread()["seen"]})
        finally:
            serve.TURN_LOCK.release()
            serve.BUDGET_S = saved
        self.assertEqual(code, 503)
        self.assertEqual(self.thread()["messages"], [])

    def test_a_write_from_another_process_meanwhile_stores_nothing(self):
        """Review finding 3: no lost update when two servers share one file."""
        def other_process_writes(req, t0=None):
            con = serve.db()
            con.execute("BEGIN IMMEDIATE"); con.execute("INSERT INTO events(at, source, event) VALUES('x', 'live', ?)", (json.dumps({"type": "resumed"}),)); con.execute("COMMIT"); con.close()
            return {"mode": "live", "intent": {"type": "answer", "topic": "unclear"}, "model": "claude-stub"}
        serve.call_claude = other_process_writes
        code, resp = serve.handle_message({"text": "anything from corvid?", "key": "k1", "seen": self.thread()["seen"]})
        self.assertEqual(code, 409)
        self.assertEqual(self.thread()["messages"], [])

    def test_a_changed_clock_reseeds_on_start(self):
        self.send("ok resume", "k1")
        con = serve.db(); serve.set_meta(con, "clock", "Mon 9:00 AM"); serve.rebuild(con); con.close()
        self.assertEqual(self.thread()["messages"], [])

    def test_a_changed_seed_reseeds_on_start(self):
        self.send("ok resume", "k1")
        con = serve.db()
        con.execute("UPDATE events SET event=? WHERE seq=1", (json.dumps({"type": "paused"}),))
        serve.rebuild(con); con.close()
        self.assertEqual((self.thread()["messages"], self.thread()["events"]), ([], 36))

    def test_bad_requests_store_nothing(self):
        self.assertEqual(serve.handle_message({"text": "", "key": "k"})[0], 400)
        self.assertEqual(serve.handle_message({"text": "hi"})[0], 400)
        self.assertEqual(self.thread()["messages"], [])


class WorkerProtocol(unittest.TestCase):
    """Review finding 4: a stray stdout line is skipped, and a hung worker is replaced, not waited on forever."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()

    def fake(self, body):
        path = os.path.join(self.dir, "worker.js")
        pathlib.Path(path).write_text(body)
        w = serve.Worker()
        self.addCleanup(stop, w)
        saved = serve.HERE
        serve.HERE = self.dir
        self.addCleanup(lambda: setattr(serve, "HERE", saved))
        return w

    def test_a_stray_line_does_not_shift_replies(self):
        w = self.fake("console.log('hello from a stray print'); console.log(JSON.stringify({id: 999, ok: true, result: 1})); console.log('42');\n"
                      "setTimeout(() => require(%r), 50);\n" % os.path.join(ROOT, "server", "worker.js"))
        self.assertEqual(len(w.call(op="seed")["events"]), 36)
        self.assertEqual(w.call(op="replay", events=[])["state"]["paused"], False)

    def test_a_hung_worker_times_out_and_is_replaced(self):
        w = self.fake("setInterval(() => {}, 1000);\n")
        with self.assertRaises(TimeoutError):
            w.call(timeout=0.5, op="seed")
        self.assertIsNone(w.p)


class Http(unittest.TestCase):
    """Review findings 5 and 6, through the real handler on a loopback port."""

    @classmethod
    def setUpClass(cls):
        import tempfile, threading, http.server
        cls.saved = serve.DB_FILE
        serve.DB_FILE = os.path.join(tempfile.mkdtemp(), "demo.db")
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        cls.port = cls.srv.server_address[1]
        serve.PORT = cls.port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()
        serve.DB_FILE = cls.saved

    def req(self, method, path, body=None, headers=None):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse(); r.read(); c.close()
        return r.status

    def test_only_the_page_files_are_served_however_spelled(self):
        """Verification 11:44, finding 1: the disk ignores case, so /SERVER/... reached server files; .git was served too."""
        for p in ["/server/serve.py", "/SERVER/serve.py", "/Server/worker.js", "/sErVeR/", "//server/serve.py", "/./server/serve.py",
                  "/%73erver/serve.py", "/tests/../server/serve.py", "/.git/HEAD", "/tests/test_server.py", "/README.md"]:
            self.assertEqual(self.req("GET", p), 404, p)
            self.assertEqual(self.req("HEAD", p), 404, "HEAD " + p)
        for p in ["/", "/index.html", "/app.js", "/core.js", "/scenes.js", "/styles.css", "/?scene=6&step=all"]:
            self.assertEqual(self.req("GET", p), 200, p)

    def test_posts_take_json_from_this_page_only(self):
        self.assertEqual(self.req("POST", "/api/reset", "{}", {"Content-Type": "text/plain"}), 403)
        self.assertEqual(self.req("POST", "/api/reset", "{}", {"Content-Type": "application/json", "Origin": "https://evil.example"}), 403)
        self.assertEqual(self.req("POST", "/api/reset", "{}", {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}"}), 200)


if __name__ == "__main__":
    unittest.main()
