"""The phone UI's markdown renderer (app.js md) on agent text: bold, lists and paragraphs render; anything else stays
escaped text. Runs app.js under node with a stub DOM (no browser, no network); skipped when node is absent."""
import json, os, re, shutil, subprocess, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED = {'p', 'br', 'strong', 'ul', 'ol', 'li'}
STUB = r"""
const vm = require('vm'), fs = require('fs');
const el = () => new Proxy({ classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } },
  addEventListener() {}, appendChild(x) { return x; }, style: {} }, { get: (t, k) => (k in t ? t[k] : ''), set: () => true });
const ctx = { window: {}, document: { getElementById: el, createElement: el, addEventListener() {}, body: el() },
  fetch: () => new Promise(() => {}), requestAnimationFrame() {}, URLSearchParams, location: { search: '' }, console };
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0, 'utf8')).map((t) => ctx.window.TsentaDemo.md(t))));
"""


def md(*texts):
    out = subprocess.run(['node', '-e', STUB, os.path.join(ROOT, 'app.js')], input=json.dumps(texts), capture_output=True,
                         text=True, timeout=30, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which('node'), 'node not installed')
class Markdown(unittest.TestCase):
    def test_preview_bold_and_lists(self):
        self.assertEqual(md("Here's the submission for approval:\n- **Company:** Peregrinefield Labs\n- **Resume:** R011, version 3\nReply **yes** to submit."),
                         ["<p>Here's the submission for approval:</p><ul><li><strong>Company:</strong> Peregrinefield Labs</li>"
                          "<li><strong>Resume:</strong> R011, version 3</li></ul><p>Reply <strong>yes</strong> to submit.</p>"])
        self.assertEqual(md('1. one\n2) two', '### Needs attention', 'line one\nline two'),
                         ['<ol><li>one</li><li>two</li></ol>', '<p><strong>Needs attention</strong></p>', '<p>line one<br>line two</p>'])

    def test_everything_else_stays_text(self):
        got = md('<img src=x onerror=alert(1)> **<b>x</b>** "q" & a', '**unclosed bold', '2 * 3 * 4', '- <script>alert(1)</script>')
        self.assertEqual(got, ['<p>&lt;img src=x onerror=alert(1)&gt; <strong>&lt;b&gt;x&lt;/b&gt;</strong> &quot;q&quot; &amp; a</p>',
                               '<p>**unclosed bold</p>', '<p>2 * 3 * 4</p>', '<ul><li>&lt;script&gt;alert(1)&lt;/script&gt;</li></ul>'])

    def test_a_real_reply_leaves_no_stars_and_only_allowed_tags(self):
        # the agent's reply to step 1 at 00:22 (gen 4, fictional P01), one bubble per blank-line part as addBubble splits it
        parts = ("You have 7 applications.\n\n**Needs attention now**\n- **Larchwick Systems (ML Engineer, Remote):** They've invited "
                 "you to interview by **today at 17:00 UTC**.\n- **Grovehaven Software (ML Engineer, Remote):** A skills assessment "
                 "is due **Oct 16 at 23:59 UTC**.").split('\n\n')
        for html in md(*parts):
            self.assertNotIn('**', html)
            self.assertLessEqual({t.lower() for t in re.findall(r'</?([a-zA-Z0-9]+)', html)}, ALLOWED, html)
            self.assertNotRegex(html, r'<[a-z]+ [^>]*>')   # no attributes anywhere


if __name__ == '__main__':
    unittest.main()
