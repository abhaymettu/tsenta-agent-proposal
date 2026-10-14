// Timed presenter dry-run at phone width: plays all five scenes at the app's own speed and
// reports wall-clock playback per scene. Next is pressed only when the app is idle (composer
// filled or "Next scene"/"Finished" showing), so nothing is hurried; talking time is not included.
// Usage: node tests/dryrun.mjs   (expects server/serve.py on 127.0.0.1:8521, or URL=...)
import { spawn } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL = process.env.URL || 'http://127.0.0.1:8521/';
const port = 9300 + Math.floor(Math.random() * 500);
const proc = spawn(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`,
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'tsenta-dryrun-'))}`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ws;
for (let i = 0; i < 50 && !ws; i++) {
  try {
    const t = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    ws = t.find((x) => x.type === 'page').webSocketDebuggerUrl;
  } catch { await sleep(100); }
}
const sock = new WebSocket(ws);
await new Promise((r) => sock.addEventListener('open', r));
let id = 0; const waiting = new Map();
sock.addEventListener('message', (m) => { const d = JSON.parse(m.data); if (waiting.has(d.id)) { waiting.get(d.id)(d); waiting.delete(d.id); } });
const cdp = (method, params = {}) => new Promise((r) => { waiting.set(++id, r); sock.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result.result.value;
const idle = `(() => { const l = document.getElementById('next').textContent;
  return document.getElementById('input').value ? 'send' : /Next scene/.test(l) ? 'scene' : /Finished/.test(l) ? 'end' : ''; })()`;

try {
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  await cdp('Page.navigate', { url: URL });
  while (!(await js(`!!window.TsentaDemo`))) await sleep(20);
  const rows = [];
  for (let scene = 1; scene <= 5; scene++) {
    const t0 = Date.now(); let sends = 0, st;
    for (;;) {
      while (!(st = await js(idle))) await sleep(20);
      if (st !== 'send') break;
      sends++; await js(`document.getElementById('next').click()`); await sleep(20);
    }
    const bubbles = await js(`document.querySelectorAll('#thread .bubble').length`);
    rows.push({ scene, ms: Date.now() - t0, sends, bubbles });
    if (scene < 5) { if (st !== 'scene') throw new Error(`scene ${scene} ended on ${st}`); await js(`document.getElementById('next').click()`); }
  }
  const total = rows.reduce((a, r) => a + r.ms, 0);
  for (const r of rows) console.log(`scene ${r.scene}: ${(r.ms / 1000).toFixed(1)} s playback, ${r.sends} sends, ${r.bubbles} bubbles in thread`);
  console.log(`total: ${(total / 1000).toFixed(1)} s playback, ${rows.reduce((a, r) => a + r.sends, 0)} sends + 4 scene advances`);
} finally { proc.kill(); }
process.exit(0);
