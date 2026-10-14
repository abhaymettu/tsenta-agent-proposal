// One message through the rules, as the backend runs it (turn.js, used by server/worker.js).
const test = require('node:test');
const assert = require('node:assert');
const Core = require('../core.js');
const SCENES = require('../scenes.js');
const { turn } = require('../turn.js');

const sceneSix = () => SCENES.flatMap((sc) => sc.steps).flatMap((st) => st.ev || []).reduce(Core.apply, Core.initial());
const CLOCK = 'Tue 10:15 AM';
// What the backend does: rules first; only when they can't answer, the model's intent.
const say = (s, q, text, intent) => { const r = turn(s, q, text, undefined, CLOCK); return r.needModel ? turn(s, q, text, intent, CLOCK) : r; };

test('rules answer first: a bare command or a status word needs no model', () => {
  const r = turn(sceneSix(), null, 'ok resume', undefined, CLOCK);
  assert.equal(r.kind, 'local');
  assert.deepEqual(r.events.map((e) => e.type), ['resumed']);
  assert.match(r.reply, /may or may not have gone through/);
  const st = turn(r.state, null, 'status', undefined, CLOCK);
  assert.equal(st.kind, 'local');
  assert.match(st.reply, /^6 applied, .*\n\n/, 'status: short lines, one bubble each');
  assert.equal(st.card, null, 'status is text, not an image card');
  assert.equal(turn(sceneSix(), null, 'yes', undefined, CLOCK).needModel, true, 'a yes with no question in the latest message goes to the model');
});

test('a consequential proposal asks; only a bare yes to that question applies, with no model call', () => {
  const s = Core.apply(sceneSix(), { type: 'resumed' });
  const ask = say(s, null, 'could you hold off on everything for now?', { type: 'pause' });
  assert.deepEqual([ask.kind, ask.events, ask.waiting], ['model', [], 'yes']);
  assert.match(ask.reply, /^Pause Tsenta\?/);
  const yes = turn(ask.state, ask.question, 'yes', undefined, CLOCK);
  assert.deepEqual([yes.kind, yes.events.map((e) => e.type)], ['local', ['paused']]);
});

test('which role: code asks, her answer is read by code, then a yes links the role she named', () => {
  const s = Core.apply(sceneSix(), { type: 'resumed' });
  const which = say(s, null, 'link the Lumen Data invite', { type: 'link', interviewId: 'I2', oppId: 'O5' });
  assert.equal(which.waiting, 'which');
  const named = turn(which.state, which.question, 'the data one', undefined, CLOCK);
  assert.match(named.reply, /to Data Platform Engineer\? Reply yes\.$/);
  const linked = turn(named.state, named.question, 'yes', undefined, CLOCK);
  assert.equal(linked.state.interviews.I2.oppId, 'O7');
});

test('a draft shows its card and asks; yes places it; a declined proposal changes nothing and is named', () => {
  const s = Core.apply(sceneSix(), { type: 'resumed' });
  const d = say(s, null, 'draft a reply to Priya', { type: 'draft', taskId: 'T-reply-I2', body: 'Hi Priya, I am free Thursday afternoon. Maya' });
  assert.equal(d.card, 'draft:A2');
  const placed = turn(d.state, d.question, 'yes', undefined, CLOCK);
  assert.equal(placed.state.actions.A2.status, 'placed');
  assert.match(placed.reply, /^Done, it's in your drafts\.\nv1 to priya@lumendata\.example\n\nSimulated here, so no real Gmail draft\. You send it, not me\.$/, 'recipient and version confirmed; the Gmail draft is never presented as real');
  const no = say(s, null, 'please resume', { type: 'resume' });
  assert.deepEqual([no.events, no.proposed], [[], 'resume']);
  assert.match(no.reply, /^That didn't go through: Tsenta isn't paused\./);
  assert.equal(JSON.stringify(no.state), JSON.stringify(s));
});
