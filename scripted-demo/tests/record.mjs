// Offline backup recordings plus desktop pixels, all from the running mock server.
//   full.mp4   all five scenes at phone width, app's own speed
//   short.mp4  ?scene=3 played, then key 5 (the short path in README "Timing")
//   desktop-scene1..5.png at 1440x900, ?scene=N&step=all&state=open
// Every video frame carries a "SIMULATION · MOCK · live model OFF" strip. Refuses to run unless
// /api/status says mode mock. Pacing on top of the app's own timers: the composer line is held
// HOLD_SEND ms before Send, a finished scene HOLD_SCENE ms before the next one.
// Usage: node tests/record.mjs <outDir>   (needs Chrome and ffmpeg; URL=... to override)
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const URL = process.env.URL || 'http://127.0.0.1:8521/';
const out = process.argv[2];
if (!out) { console.error('usage: node tests/record.mjs <outDir>'); process.exit(2); }
const HOLD_SEND = 1200, HOLD_SCENE = 2500, STRIP = 104;
const LABEL = 'SIMULATION · MOCK · LIVE MODEL OFF<br><span style="font-weight:500">Synthetic data. Nothing is sent.</span>';

const status = await (await fetch(new globalThis.URL('api/status', URL))).json();
if (status.mode !== 'mock') { console.error('refusing to record: server mode is', status.mode); process.exit(1); }

mkdirSync(out, { recursive: true });
const port = 9300 + Math.floor(Math.random() * 500);
const proc = spawn(CHROME, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`,
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'tsenta-record-'))}`, 'about:blank'], { stdio: 'ignore' });
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
let id = 0; const waiting = new Map(); let onFrame = null;
sock.addEventListener('message', (m) => {
  const d = JSON.parse(m.data);
  if (waiting.has(d.id)) { waiting.get(d.id)(d); waiting.delete(d.id); }
  else if (d.method === 'Page.screencastFrame') onFrame?.(d.params);
});
const cdp = (method, params = {}) => new Promise((r) => { waiting.set(++id, r); sock.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result.result.value;
const idle = `(() => { const l = document.getElementById('next').textContent;
  return document.getElementById('input').value ? 'send' : /Next scene/.test(l) ? 'scene' : /Finished/.test(l) ? 'end' : ''; })()`;
const phone = () => cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
const open = async (url) => { await cdp('Page.navigate', { url }); await sleep(300); while (!(await js(`!!window.TsentaDemo`))) await sleep(20); };
const key = async (k) => { for (const type of ['keyDown', 'keyUp']) await cdp('Input.dispatchKeyEvent', { type, key: k, code: 'Digit' + k, text: type === 'keyDown' ? k : undefined }); };

// Play the current scene to its end, holding on each composer line before Send.
async function playScene() {
  for (;;) {
    let st; while (!(st = await js(idle))) await sleep(20);
    if (st !== 'send') return st;
    await sleep(HOLD_SEND);
    await js(`document.getElementById('next').click()`);
    await sleep(40);
  }
}

// Screencast frames are emitted on change only; each frame lasts until the next one.
async function record(name, script) {
  const dir = mkdtempSync(join(tmpdir(), `tsenta-${name}-`)); const frames = [];
  onFrame = (p) => {
    const f = join(dir, `f${String(frames.length).padStart(5, '0')}.jpg`);
    writeFileSync(f, Buffer.from(p.data, 'base64')); frames.push({ f, t: p.metadata.timestamp });
    cdp('Page.screencastFrameAck', { sessionId: p.sessionId });
  };
  await cdp('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 780, maxHeight: 1688 });
  await sleep(500);
  const t0 = Date.now(); await script(); const ms = Date.now() - t0;
  await sleep(HOLD_SCENE);
  await cdp('Page.stopScreencast'); onFrame = null;
  const end = frames.at(-1).t + HOLD_SCENE / 1000;
  const list = frames.map((fr, i) => `file '${fr.f}'\nduration ${((frames[i + 1]?.t ?? end) - fr.t).toFixed(3)}`).join('\n') + `\nfile '${frames.at(-1).f}'\n`;
  writeFileSync(join(dir, 'list.txt'), list);
  const mp4 = join(out, `${name}.mp4`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(dir, 'list.txt'), '-i', join(out, 'label.png'),
    '-filter_complex', `[0:v]fps=30,scale=780:1688,pad=780:${1688 + STRIP}:0:0:white[v];[v][1:v]overlay=0:${1688}`,
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4]);
  const secs = +execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4]).toString();
  console.log(`${name}.mp4: ${secs.toFixed(1)} s video (${(ms / 1000).toFixed(1)} s scripted run), ${frames.length} frames`);
}

try {
  // Label strip, rendered once by Chrome itself (this ffmpeg has no drawtext).
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: STRIP / 2, deviceScaleFactor: 2, mobile: true });
  await cdp('Page.navigate', { url: 'data:text/html,' + encodeURIComponent(`<meta charset="utf-8"><meta name="viewport" content="width=device-width"><body style="margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#fff3cd;font:700 15px/1.35 -apple-system,system-ui;letter-spacing:0.02em;color:#664d03;text-align:center;padding:0 8px;box-sizing:border-box">${LABEL}</body>`) });
  await sleep(300);
  writeFileSync(join(out, 'label.png'), Buffer.from((await cdp('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'));

  await phone(); await open(URL);
  if (!/^Mode: scripted/.test(await js(`document.getElementById('mode-line').textContent`))) throw new Error('mode line is not scripted');
  await record('full', async () => {
    for (let s = 1; s <= 5; s++) {
      const st = await playScene();
      if (s < 5) { if (st !== 'scene') throw new Error(`scene ${s} ended on ${st}`); await sleep(HOLD_SCENE); await js(`document.getElementById('next').click()`); }
    }
  });
  const full = await js(`document.querySelectorAll('#thread .bubble').length`);

  await phone(); await open(new globalThis.URL('?scene=3', URL).href);
  await record('short', async () => {
    await playScene(); await sleep(HOLD_SCENE);
    await key('5'); await sleep(100); await playScene();
  });
  const short = await js(`JSON.stringify({ scene: TsentaDemo.scene(), bubbles: document.querySelectorAll('#thread .bubble').length })`);
  console.log(`thread at end: full ${full} bubbles; short ${short}`);

  await cdp('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 2, mobile: false });
  for (let s = 1; s <= 5; s++) {
    await open(new globalThis.URL(`?scene=${s}&step=all&state=open`, URL).href); await sleep(600);
    writeFileSync(join(out, `desktop-scene${s}.png`), Buffer.from((await cdp('Page.captureScreenshot', { format: 'png' })).result.data, 'base64'));
  }
  console.log('desktop-scene1..5.png written');
} finally { proc.kill(); }
process.exit(0);
