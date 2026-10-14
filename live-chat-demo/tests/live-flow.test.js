// The browser side of live mode: a thin client of the demo backend. It renders what the backend stored, sends `seen`
// (agent messages on screen) and an idempotency key fixed at send time, and never applies rules itself.
const test = require('node:test');
const assert = require('node:assert');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const SCENES = require('../scenes.js');

const src = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
const body = src.slice(src.indexOf('  let liveQueue = Promise.resolve()'), src.indexOf('  async function detectLive()'));

// respond: (requestBody) => { status, json } | 'throw' | Promise
function harness(respond, init = {}) {
  const events = [];
  const el = (cls) => ({ cls, remove: () => events.push(['remove', cls]) });
  const ctx = Object.assign({
    state: { tag: 'before' }, rebuild: 0, seen: 2, threadLoaded: true, live: { backend: true }, busy: false, pendingUser: null,
    scene: SCENES.length - 1, pos: 0, STEPS: [], SCENES, hurry() {}, AbortSignal: { timeout: () => undefined },
    setTimeout, goTo: async () => events.push(['goTo']), modeLine: { textContent: 'Mode' }, $: () => ctx.modeLine,
    crypto: { randomUUID: (() => { let n = 0; return () => 'k' + ++n; })() }, esc: (x) => String(x),
    setComposer: (x) => events.push(['composer', x]), renderState: () => events.push(['render', ctx.state.tag]),
    addBubble: (who, text, tag) => events.push(['bubble', who, text, tag]), addCard: (name, s) => events.push(['card', name, s && s.tag]),
    div: (cls, html) => Object.assign(el(cls), { html }), append: (d) => { events.push(['append', d.cls, d.html]); return d; },
    fetch: async (url, opts) => {
      const req = opts && opts.body ? JSON.parse(opts.body) : null;
      events.push(['fetch', url, req]);
      const r = await respond(req, url);
      if (r === 'throw') throw new Error('offline');
      return { ok: r.status === 200, status: r.status, json: async () => r.json };
    },
  }, init);
  vm.createContext(ctx);
  vm.runInContext(body + '\nglobalThis.sendLive = sendLive; globalThis.loadThread = loadThread; globalThis.resetAll = resetAll; globalThis.setLoading = (v) => { loading = v; };', ctx);
  return { ctx, events };
}
const stored = (rows, extra) => ({ status: 200, json: Object.assign({ messages: rows, state: { tag: 'after' }, seen: 3 }, extra) });

test('a message goes to the backend with its key and the agent messages seen at send; stored rows are rendered', async () => {
  const { ctx, events } = harness(() => stored([
    { who: 'me', text: 'draft a reply to Priya' },
    { who: 'them', text: "Here's v1 to priya@lumendata.example.", tag: 'Claude · haiku-5-5 · 1.2 s · reply written by code', card: 'draft:A2', cardState: { tag: 'card' } },
    { who: 'sys', text: 'Code accepted: draft, ask_approval' },
  ]));
  await ctx.sendLive('draft a reply to Priya');
  const f = events.find((e) => e[0] === 'fetch');
  assert.deepEqual([f[1], f[2]], ['/api/message', { text: 'draft a reply to Priya', key: 'k1', seen: 2 }]);
  assert.deepEqual(events.filter((e) => e[0] === 'bubble').map((e) => e[1]), ['me', 'them'], 'her bubble once, then the stored reply');
  assert.deepEqual(events.find((e) => e[0] === 'card'), ['card', 'draft:A2', 'card'], 'the card shows the state stored with it');
  assert.ok(events.some((e) => e[0] === 'append' && e[1] === 'sys' && /Code accepted/.test(e[2])));
  assert.equal(ctx.state.tag, 'after');
  assert.equal(ctx.seen, 3);
});

test('seen is fixed when she presses send: a yes typed before a reply lands carries the older count', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  let n = 0;
  const { ctx, events } = harness(async () => { n++; if (n === 1) await gate; return stored([{ who: 'them', text: 'ok' }], { seen: 2 + n }); });
  const a = ctx.sendLive('suggest a route'), b = ctx.sendLive('yes');
  release(); await a; await b;
  assert.deepEqual(events.filter((e) => e[0] === 'fetch').map((e) => e[2].seen), [2, 2], 'the backend sees the yes predates the newer reply');
});

test('a reply the backend did not store makes seen -1, so the next message answers no earlier question', async () => {
  let n = 0;
  const { ctx, events } = harness(() => (++n === 1 ? 'throw' : stored([{ who: 'them', text: 'ok' }])));
  await ctx.sendLive('anything from corvid?');
  const note = events.filter((e) => e[0] === 'bubble' && e[1] === 'them').at(-1);
  assert.deepEqual([note[2], note[3]], ['The demo backend is unavailable right now, so nothing was shown or changed. Try again.', 'not stored']);
  assert.equal(ctx.seen, -1);
  await ctx.sendLive('yes');
  assert.equal(events.filter((e) => e[0] === 'fetch').at(-1)[2].seen, -1);
});

test('a response that arrives after a scene jump or reset is dropped', async () => {
  let ctxRef;
  const { ctx, events } = harness(() => { ctxRef.rebuild++; return stored([{ who: 'them', text: 'late' }]); });
  ctxRef = ctx;
  await ctx.sendLive('status');
  assert.ok(!events.some((e) => e[0] === 'bubble' && e[1] === 'them'));
  assert.equal(ctx.state.tag, 'before');
});

test('before the scene-6 thread is loaded nothing is sent; loading renders the stored thread and its count', async () => {
  const { ctx, events } = harness((req, url) => ({ status: 200, json: { state: { tag: 'db' }, messages: [{ who: 'me', text: 'hi' }, { who: 'them', text: 'hello', tag: 't' }], seen: 1, events: 40, seededAt: '2026-10-13T11:00:00' } }), { threadLoaded: false, seen: -1 });
  await ctx.sendLive('hello?');
  assert.ok(!events.some((e) => e[0] === 'fetch'));
  assert.equal(events.filter((e) => e[0] === 'bubble').at(-1)[3], 'not stored');
  await ctx.loadThread();
  assert.deepEqual([ctx.state.tag, ctx.seen, ctx.threadLoaded], ['db', 1, true]);
  assert.ok(events.some((e) => e[0] === 'append' && /40 events in SQLite, seeded demo data/.test(e[2])));
});

test('a message typed while the stored thread loads goes after it, not above it (verification 11:44, finding 3)', async () => {
  const { ctx, events } = harness(() => stored([{ who: 'them', text: 'new' }]));
  ctx.setLoading(true);
  const p = ctx.sendLive('hello');
  await new Promise((r) => setTimeout(r, 20));
  assert.ok(!events.some((e) => e[0] === 'bubble'), 'nothing drawn while the thread loads');
  events.push(['loaded']); ctx.setLoading(false);
  await p;
  assert.deepEqual(events.filter((e) => e[0] === 'bubble' || e[0] === 'loaded').map((e) => e[1] || e[0]), ['loaded', 'me', 'them']);
});

test('reset: only a message already in flight reaches the backend; queued ones are dropped silently; a failed reset is reported', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const { ctx, events } = harness(async (req, url) => (url === '/api/reset' ? { status: 500, json: {} } : (await gate, stored([{ who: 'them', text: 'late' }]))));
  ctx.sendLive('first'); ctx.sendLive('second');
  await new Promise((r) => setTimeout(r, 10));
  const reset = ctx.resetAll();
  release(); await reset;
  assert.deepEqual(events.filter((e) => e[0] === 'fetch').map((e) => e[1]), ['/api/message', '/api/reset']);
  assert.deepEqual(events.filter((e) => e[0] === 'bubble').map((e) => e[2]), ['first'], 'no reply and no note for the queued message');
  assert.ok(events.some((e) => e[0] === 'goTo'));
  assert.match(ctx.modeLine.textContent, /reset failed: the stored thread is unchanged/);
});
