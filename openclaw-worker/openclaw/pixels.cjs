// G10 pixels (548 s11): desktop and phone-width screenshots of the stored thread, read-only. Playwright's bundled headless
// Chromium (never the user's Chrome); every non-GET request is aborted, so no key press, reset or message can reach the
// core. Per viewport: the thread top, the thread bottom, and the last-turn receipt panel (a local toggle). Checks: no
// horizontal overflow, the sandbox disclosure visible, no key-shaped token, no real-name hit, 0 POSTs attempted.
// Usage: node openclaw/pixels.cjs <url> <out dir>   (exit 0 PASS, 1 FAIL)
const { chromium } = require('playwright-core');
// Real-name leak check: set REAL_NAMES_RE (a regex) to the names that must never render.
const REAL_NAMES = new RegExp(process.env.REAL_NAMES_RE || '(?!)');
const fs = require('fs'), crypto = require('crypto');
const [,, url, out] = process.argv;
if (!url || !out) { console.error('usage: node openclaw/pixels.cjs <url> <out dir>'); process.exit(2); }
fs.mkdirSync(out, { recursive: true });
let fails = 0;
const check = (name, ok, got) => { console.log(`${ok ? 'ok  ' : 'FAIL'}  ${name} = ${got}`); if (!ok) fails++; };
(async () => {
  // Playwright's own headless browser, never the user's Chrome. PW_CHROMIUM may name another headless build's executable.
  const b = await chromium.launch({ headless: true, ...(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {}) });
  for (const [name, vp] of [['desktop', { width: 1440, height: 900 }], ['phone', { width: 390, height: 844 }]]) {
    const p = await b.newPage({ viewport: vp, deviceScaleFactor: 2 });
    let blocked = 0;
    await p.route('**/*', (r) => (r.request().method() === 'GET' ? r.continue() : (blocked++, r.abort())));
    await p.goto(url);
    await p.waitForFunction(() => document.querySelectorAll('#thread > *').length > 1, null, { timeout: 15000 });
    await p.waitForTimeout(600);
    await p.evaluate(() => { document.getElementById('thread').scrollTop = 0; });
    await p.screenshot({ path: `${out}/${name}-1-thread-top.png` });
    await p.evaluate(() => { const t = document.getElementById('thread'); t.scrollTop = t.scrollHeight; });
    await p.waitForTimeout(300);
    await p.screenshot({ path: `${out}/${name}-2-thread-bottom.png` });
    await p.click(name === 'desktop' ? '#r-state' : '#m-state').catch((e) => console.log('info  receipt toggle', e.message.slice(0, 80)));
    await p.waitForTimeout(500);
    await p.screenshot({ path: `${out}/${name}-3-receipt.png` });
    const m = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth,
      disc: (() => { const d = document.querySelector('.disclosure'); return !!d && d.getBoundingClientRect().height > 0; })(),
      text: document.body.innerText, bubbles: document.querySelectorAll('#thread .msg').length }));
    console.log(`info  ${name} bubbles ${m.bubbles}`);
    check(`${name} no horizontal overflow (scrollWidth <= innerWidth)`, m.sw <= m.iw, `${m.sw} / ${m.iw}`);
    check(`${name} sandbox disclosure rendered`, m.disc, m.disc);
    check(`${name} key-shaped tokens on the page`, !m.text.includes('sk-ant-'), m.text.includes('sk-ant-') ? 'present' : 0);
    check(`${name} real-name check`, !REAL_NAMES.test(m.text), REAL_NAMES.test(m.text) ? 'HIT' : 'clean');
    check(`${name} non-GET requests attempted (all aborted)`, blocked === 0, blocked);
    await p.close();
  }
  await b.close();
  for (const f of fs.readdirSync(out).filter((f) => f.endsWith('.png')).sort())
    console.log(`info  ${f} sha256 ${crypto.createHash('sha256').update(fs.readFileSync(`${out}/${f}`)).digest('hex').slice(0, 16)}`);
  console.log(`RESULT: ${fails ? `FAIL (${fails})` : 'PASS'}`);
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.log('FAIL ', e.message); process.exit(1); });
