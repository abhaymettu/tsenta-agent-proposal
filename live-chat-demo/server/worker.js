// The backend's rules engine: serve.py keeps one of these running and sends it one JSON line per request; each reply
// echoes the request's id. Nothing else may write to stdout. It runs the
// same reducer, intent checks and reply templates as the browser, so there is one set of rules, not a port.
//   {op:'seed'}                                   -> {events, clock}: the labelled demo data (scenes 1 to 6)
//   {op:'replay', events}                         -> {state}
//   {op:'turn', state, question, text, intent?, clock} -> turn.js result
const path = require('node:path');
const readline = require('node:readline');
const R = path.join(__dirname, '..');
const Core = require(path.join(R, 'core.js'));
const SCENES = require(path.join(R, 'scenes.js'));
const { turn } = require(path.join(R, 'turn.js'));
const FX = require(path.join(R, 'fixtures.js'));

// Facts the model may cite, computed by code. Reply status never comes from the model.
function facts(s, clock) {
  const replies = {};
  for (const o of Object.values(s.opps)) {
    replies[o.id] = { employer: o.employer, role: o.role, receipt: o.receipt };
    if (o.receipt === 'confirmed') replies[o.id].reply = Core.replyStatus(s, o.id);
  }
  return { replies, clock, routeOptions: Object.keys(FX.routes).map((id) => ({ id, to: FX.routes[id].to })) };
}

function seed() {
  const steps = SCENES.flatMap((sc) => sc.steps);
  const events = steps.flatMap((st) => st.ev || []);
  const times = steps.filter((st) => st.t === 'time');
  return { events, clock: times.length ? times[times.length - 1].text : '' };
}

const OPS = {
  seed,
  replay: (m) => ({ state: m.events.reduce(Core.apply, Core.initial()) }),
  turn: (m) => {
    const r = turn(m.state, m.question, m.text, m.intent == null ? undefined : m.intent, m.clock);
    return r.needModel ? { needModel: true, facts: facts(m.state, m.clock) } : r;
  },
};

readline.createInterface({ input: process.stdin }).on('line', (line) => {
  let out, id = null;
  try {
    const m = JSON.parse(line);
    id = m.id;
    out = { id, ok: true, result: OPS[m.op](m) };
  } catch (err) {
    out = { id, ok: false, error: String(err && err.message || err) };
  }
  process.stdout.write(JSON.stringify(out) + '\n');
});
