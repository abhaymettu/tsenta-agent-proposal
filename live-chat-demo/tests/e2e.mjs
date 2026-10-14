// End-to-end check at phone width: clicks Next through all scenes like a presenter would,
// asserts the final state, and saves a screenshot per scene.
// Usage: node tests/e2e.mjs [outDir]   (expects server/serve.py on 127.0.0.1:8521)
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL = process.env.URL || 'http://127.0.0.1:8521/';
const out = process.argv[2];
const port = 9300 + Math.floor(Math.random() * 500);
const proc = spawn(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`,
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'tsenta-e2e-'))}`, 'about:blank'], { stdio: 'ignore' });
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

const fail = (msg) => { console.error('FAIL', msg); proc.kill(); process.exit(1); };
try {
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  await cdp('Page.navigate', { url: URL });
  await sleep(800);
  if (out) mkdirSync(out, { recursive: true });
  for (let scene = 1; scene <= 5; scene++) {
    // Press Next until this scene finishes (button reads "Next scene" or "Finished").
    for (let n = 0; n < 60; n++) {
      const label = await js(`document.getElementById('next').textContent`);
      if (/Next scene|Finished/.test(label)) break;
      await js(`document.getElementById('next').click()`);
      await sleep(1600);
    }
    const overflow = await js(`document.documentElement.scrollWidth > innerWidth || [...document.querySelectorAll('#thread > *')].some(e => e.getBoundingClientRect().right > innerWidth + 1)`);
    if (overflow) fail(`horizontal overflow in scene ${scene}`);
    if (out) {
      const shot = await cdp('Page.captureScreenshot', { format: 'png' });
      writeFileSync(join(out, `phone-scene${scene}.png`), Buffer.from(shot.result.data, 'base64'));
    }
    if (scene < 5) { await js(`document.getElementById('next').click()`); await sleep(300); }
  }
  const s = await js(`JSON.stringify((() => { const t = [...document.querySelectorAll('#thread .bubble')].map(b => b.textContent); return { bubbles: t.length, last: t.at(-1) }; })())`);
  const r = JSON.parse(s);
  if (!/undo/.test(r.last)) fail('demo did not reach the final scene: ' + r.last);
  const log = await js(`[...document.querySelectorAll('.log .ignored')].length`);

  // Controls, with state proof from the core (window.TsentaDemo), not from bubble text.
  const key = async (k, code) => {
    for (const type of ['keyDown', 'keyUp']) await cdp('Input.dispatchKeyEvent', { type, key: k, code, text: type === 'keyDown' && k.length === 1 ? k : undefined });
    await sleep(900);
  };
  const st = async () => JSON.parse(await js(`JSON.stringify({ scene: TsentaDemo.scene(), s: TsentaDemo.state() })`));
  await js('document.activeElement.blur()');
  await key('r', 'KeyR');
  let c = await st();
  if (c.scene !== 0 || Object.keys(c.s.opps).length || Object.keys(c.s.interviews).length || c.s.route) fail('R did not reset to a clean scene 1: ' + JSON.stringify({ scene: c.scene, opps: Object.keys(c.s.opps), route: c.s.route }));
  await sleep(3000); // let scene 1's opening auto-play settle
  const bubbles = () => js(`document.querySelectorAll('#thread .bubble').length`);
  const b0 = await bubbles();
  await key(' ', 'Space');
  c = await st();
  if (c.scene !== 0 || (await bubbles()) <= b0) fail('Space did not advance within scene 1');
  await key('4', 'Digit4');
  c = await st();
  if (c.scene !== 3 || c.s.actions.A1?.status !== 'retired' || c.s.opps.O3?.receipt !== 'confirmed' || c.s.route) fail('4 did not jump to scene 4 with scenes 1-3 applied');
  await key('ArrowLeft', 'ArrowLeft');
  c = await st();
  if (c.scene !== 2 || ['confirmed', 'cancelled'].includes(c.s.interviews.I1?.status)) fail('ArrowLeft did not go back to scene 3 without scene 4 events');

  // Typed text in mock mode: a canned reply that says it is scripted, and no state change.
  await sleep(5000); // let scene 3's auto-play finish so only the typed message could change state
  const before = (await st()).s.log.length;
  await js(`(() => { const i = document.getElementById('input'); if (i.readOnly) return; i.focus(); i.value = 'what is the weather today'; i.dispatchEvent(new Event('input')); document.getElementById('send').click(); })()`);
  for (let n = 0; n < 20 && (await js(`!!document.querySelector('#thread .typing')`)); n++) await sleep(250);
  await sleep(1200);
  c = await st();
  const last = JSON.parse(await js(`JSON.stringify((() => { const m = [...document.querySelectorAll('#thread .msg')]; const i = m.findIndex((e) => e.classList.contains('me') && e.textContent.includes('what is the weather today')); return m.slice(i + 1).find((e) => e.classList.contains('them'))?.textContent || 'no typed bubble'; })())`));
  if (!/scripted/i.test(last) || c.s.log.length !== before) fail('typed mock reply missing the scripted fallback or changed state: ' + last);
  console.log(`PASS: ${r.bubbles} bubbles across 5 scenes at 390px, no overflow; ignored-event lines in log view: ${log}; controls R/Space/4/ArrowLeft and typed mock fallback verified against core state`);
} finally { proc.kill(); }
process.exit(0);
