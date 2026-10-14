// Browser canary for the fill route (operator 19:23): a non-activating offscreen WKWebView (no window, no Dock icon,
// no focus; never Chrome) loads the real fill page, so the POST carries a real browser Origin and runs under the page's
// CSP. The FAKE key is generated inside the page with crypto.getRandomValues ("sk-ant-canary-" + 48 hex), typed into the
// password field and submitted through the page's own handler. It is never in this process's argv or output. canary.sh
// learns it afterwards only by reading it back from the container's tmpfs.
// Usage: fill-browser <route url>      prints the page's status line and the inputs left in the DOM, e.g.
//   "filled: yes" then "dom-inputs: 0" (exit 0 only for both)
import AppKit
import WebKit
let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
guard CommandLine.arguments.count == 2, let url = URL(string: CommandLine.arguments[1]), url.host == "127.0.0.1" else {
  print("usage: fill-browser http://127.0.0.1:<port>/fill/<token>"); exit(2)
}
final class Runner: NSObject, WKNavigationDelegate {
  let view: WKWebView
  override init() {
    let c = WKWebViewConfiguration(); c.websiteDataStore = .nonPersistent()
    view = WKWebView(frame: NSRect(x: 0, y: 0, width: 600, height: 400), configuration: c)
    super.init(); view.navigationDelegate = self
  }
  func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
    let fill = """
      (() => { const b = new Uint8Array(24); crypto.getRandomValues(b);
        const k = document.getElementById('k'); k.focus();
        k.value = 'sk-ant-canary-' + Array.from(b, x => x.toString(16).padStart(2, '0')).join('');
        k.dispatchEvent(new Event('input', { bubbles: true }));
        document.getElementById('f').requestSubmit(); return 'submitted'; })()
      """
    view.evaluateJavaScript(fill) { _, e in if e != nil { print("filled: no (page script error)"); exit(1) }; self.poll(0) }
  }
  func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { print("filled: no (load failed)"); exit(1) }
  func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { print("filled: no (load failed)"); exit(1) }
  func poll(_ n: Int) {
    view.evaluateJavaScript("document.getElementById('r').textContent") { v, _ in
      let t = (v as? String) ?? ""
      if t.hasPrefix("filled:") || n > 150 {
        self.view.evaluateJavaScript("document.querySelectorAll('input').length") { c, _ in
          let inputs = (c as? Int) ?? -1
          print(t.isEmpty ? "filled: no (no answer)" : t); print("dom-inputs: \(inputs)")
          exit(t == "filled: yes" && inputs == 0 ? 0 : 1)
        }
        return
      }
      DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { self.poll(n + 1) }
    }
  }
}
let r = Runner()
r.view.load(URLRequest(url: url))
app.run()
