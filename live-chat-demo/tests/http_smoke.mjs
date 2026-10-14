// Real path, no browser: POST /api/agent on a running variant server, then the same checks the browser runs
// (intents.js -> core.js -> status model). In live mode each message is one paid model call.
// Usage: URL=http://127.0.0.1:8526 node tests/http_smoke.mjs ["message" ...]
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const Core = require('../core.js'), FX = require('../fixtures.js'), { toEvents } = require('../intents.js'), { statusText } = require('../status.js'), { say } = require('../voice.js');

const URL = process.env.URL || 'http://127.0.0.1:8526';
const states = JSON.parse(execFileSync('node', [new globalThis.URL('./make-eval-states.js', import.meta.url).pathname]));
const msgs = process.argv.slice(2).length ? process.argv.slice(2) : ['where do things stand?', 'did the Corvid one go through?'];

for (const text of msgs) {
  const base = states.resumed;
  const t0 = Date.now();
  const res = await fetch(`${URL}/api/agent`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...base, userText: text }) });
  const j = await res.json();
  const o = toEvents(base.state, j.intent, FX, text);
  const s = o.ok ? o.events.reduce(Core.apply, base.state) : base.state;
  console.log(`${res.status} ${Date.now() - t0} ms ${j.mode}/${j.model} intent=${JSON.stringify(j.intent && { type: j.intent.type, topic: j.intent.topic, oppId: j.intent.oppId })}`);
  console.log(`  reply (written by code): ${j.mode === 'live' ? say(base.state, s, j.intent, o) : j.reply}`);
  console.log(`  code: ${o.ok ? `accepted [${o.events.map((e) => e.type)}] card=${o.card}` : `declined: ${o.reason}`}`);
  if (o.card && o.card.startsWith('status:')) console.log(`  status text: ${statusText(s, o.card.split(':')[1], 'Tue 10:15 AM').slice(0, 240)}...`);
  if (o.ok && o.events.some((e) => e.type === 'reconciled')) console.log(`  O8 now: ${s.opps.O8.receipt} (${s.opps.O8.evidence})`);
}
