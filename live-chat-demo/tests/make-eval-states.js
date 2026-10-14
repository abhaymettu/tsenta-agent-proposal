// Prints the fixture states used by tests/live_eval.mjs and tests/http_smoke.mjs, with the same `facts` the browser sends.
const Core = require('../core.js');
const SCENES = require('../scenes.js');
const FX = require('../fixtures.js');
const { toEvents } = require('../intents.js');

let s = Core.initial();
for (const sc of SCENES) for (const st of sc.steps) for (const e of st.ev || []) s = Core.apply(s, e);
const apply = (st, intent) => { const r = toEvents(st, intent, FX, 'ok resume'); if (!r.ok) throw new Error(r.reason); return r.events.reduce(Core.apply, st); };
const facts = (st) => {
  const replies = {};
  for (const o of Object.values(st.opps)) {
    replies[o.id] = { employer: o.employer, role: o.role, receipt: o.receipt };
    if (o.receipt === 'confirmed') replies[o.id].reply = Core.replyStatus(st, o.id);
  }
  return { replies, clock: 'Tue 10:15 AM', routeOptions: Object.entries(FX.routes).map(([id, r]) => ({ id, to: r.to })) };
};
const paused = s;
const resumed = apply(paused, { type: 'resume' });
const drafted = apply(resumed, { type: 'draft', taskId: 'T-reply-I2', body: "Hi Priya, thanks for reaching out. I applied to both the Backend Engineer and Data Platform Engineer roles; which one is this for? I'm free Thursday afternoon. Best, Maya" });
const out = {};
for (const [k, st] of Object.entries({ paused, resumed, drafted })) out[k] = { scene: 6, state: st, pending: st.pending, facts: facts(st) };
process.stdout.write(JSON.stringify(out));
