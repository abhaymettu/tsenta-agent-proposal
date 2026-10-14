# Run: python3 -m unittest discover tests
import importlib.util, json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
import serve  # noqa: E402



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


if __name__ == "__main__":
    unittest.main()
