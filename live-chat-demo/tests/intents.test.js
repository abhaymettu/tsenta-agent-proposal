// Intent contract: what a model proposal can and cannot do, checked through the real reducer.
const test = require('node:test');
const assert = require('node:assert');
const Core = require('../core.js');
const SCENES = require('../scenes.js');
const FX = require('../fixtures.js');
const { toEvents, local, isYes } = require('../intents.js');

// State at the end of scene 6 ("Your turn"): paused mid-submit on Corvid (O8), Priya's invite I2 unlinked.
const live = () => {
  let s = Core.initial();
  for (const sc of SCENES) for (const st of sc.steps) for (const e of st.ev || []) s = Core.apply(s, e);
  return s;
};
const blank = { taskId: '', actionId: '', version: 0, recipient: '', epoch: 0, body: '', oppId: '', interviewId: '', routeId: '', section: '' };
const I = (type, f) => Object.assign({}, blank, { type }, f);
// Propose, check, confirm with a local "yes" when code asks, apply: the same path the browser takes.
// For link, Maya's words name the proposed role (otherwise code asks which role).
const step = (s, intent, text = intent.type === 'link' && s.opps[intent.oppId] ? s.opps[intent.oppId].role : 'x') => {
  let r = toEvents(s, intent, FX, text);
  if (r.confirm) r = local(s, r.confirm, 'yes', FX);
  return { r, s: r.ok ? r.events.reduce(Core.apply, s) : s };
};

test('scene 6 sets up the live state', () => {
  const s = live();
  assert.equal(s.paused, true);
  assert.equal(s.opps.O8.receipt, 'in_flight');
  assert.equal(s.interviews.I2.oppId, null);
});

test('pause and resume map to the reducer events (the old pause/paused mismatch is gone)', () => {
  let { r, s } = step(live(), I('pause'));
  assert.equal(r.ok, false, 'already paused');
  ({ r, s } = step(s, I('resume')));
  assert.deepEqual(r.events.map((e) => e.type), ['resumed']);
  assert.equal(s.paused, false);
  assert.equal(s.opps.O8.receipt, 'unknown_effect', 'resume turns in-flight into unknown-effect, never a retry');
  ({ r, s } = step(s, I('pause')));
  assert.equal(r.ok, true);
  assert.equal(s.paused, true);
});

test('reconcile uses fixture evidence only, and only for unknown-effect work', () => {
  let { r, s } = step(live(), I('reconcile', { oppId: 'O8' }));
  assert.equal(r.ok, false, 'still in flight before resume');
  assert.match(r.reason, /Resume first/);
  ({ s } = step(s, I('resume')));
  ({ r, s } = step(s, I('reconcile', { oppId: 'O8' })));
  assert.equal(r.ok, true);
  assert.equal(s.opps.O8.receipt, 'confirmed');
  assert.match(s.opps.O8.evidence, /staged/);
  ({ r } = step(s, I('reconcile', { oppId: 'O2' })));
  assert.equal(r.ok, false, 'an attempt with no receipt cannot be talked into confirmed');
  ({ r } = step(s, I('reconcile', { oppId: 'O9' })));
  assert.equal(r.ok, false);
});

test('no fixture evidence means it stays unknown', () => {
  let s = live();
  s = Core.apply(s, { type: 'opp_added', id: 'O9', employer: 'Nimbus', role: 'SRE', receipt: 'queued' });
  s = Core.apply(s, { type: 'submit_started', oppId: 'O9' });
  ({ s } = step(s, I('resume')));
  const { r } = step(s, I('reconcile', { oppId: 'O9' }));
  assert.equal(r.ok, false);
  assert.match(r.reason, /no portal evidence/);
  assert.equal(s.opps.O9.receipt, 'unknown_effect');
});

test('draft: code picks id and recipient; the model cannot address it', () => {
  let { r, s } = step(live(), I('draft', { taskId: 'T-reply-I2', body: 'Hi Priya', recipient: 'attacker@example.com' }));
  assert.equal(r.ok, false, 'paused');
  ({ s } = step(s, I('resume')));
  ({ r, s } = step(s, I('draft', { taskId: 'T-reply-I2', body: 'Hi Priya, which role is this for?', recipient: 'attacker@example.com' })));
  assert.equal(r.ok, true);
  assert.equal(s.actions.A2.recipient, 'priya@lumendata.example');
  assert.deepEqual(s.pending, { actionId: 'A2', version: 1, recipient: 'priya@lumendata.example', epoch: s.epoch });
  assert.equal(r.card, 'draft:A2');
  ({ r } = step(s, I('draft', { taskId: 'T-reply-I2', body: 'again' })));
  assert.equal(r.ok, false, 'one live draft per task; ask for a new version instead');
  ({ r } = step(s, I('draft', { taskId: 'T-reply-I1', body: 'x' })));
  assert.equal(r.ok, false, 'Halyard reply was done by hand in scene 4');
  ({ r } = step(s, I('draft', { taskId: 'T-reply-I2', body: '' })));
  assert.equal(r.ok, false);
});

const withDraft = () => {
  let { s } = step(live(), I('resume'));
  ({ s } = step(s, I('draft', { taskId: 'T-reply-I2', body: 'v1' })));
  return s;
};

test('redraft makes a new version and moves the open question to it', () => {
  const { r, s } = step(withDraft(), I('redraft', { actionId: 'A2', body: 'v2 warmer' }));
  assert.equal(r.ok, true);
  assert.equal(s.actions.A2.versions.length, 2);
  assert.equal(s.pending.version, 2);
});

test('approve is built from the open question in state, never from model fields, and only on a yes', () => {
  const s = step(withDraft(), I('redraft', { actionId: 'A2', body: 'v2' })).s;
  const r = toEvents(s, I('approve', { actionId: 'A1', version: 9, recipient: 'attacker@example.com', epoch: 0 }), FX, 'yes');
  assert.ok(r.confirm, 'a model approve only asks');
  assert.equal(r.confirm.question, 'Put v2 to priya@lumendata.example in your Gmail drafts? Reply yes. You send it, not me.');
  const { r: done, s: after } = step(s, I('approve', { actionId: 'A1', recipient: 'attacker@example.com' }));
  assert.equal(done.ok, true);
  assert.deepEqual(done.events[0], { type: 'yes', actionId: 'A2', version: 2, recipient: 'priya@lumendata.example', epoch: s.epoch });
  assert.equal(after.actions.A2.status, 'placed');
  assert.equal(after.pending, null);
  assert.equal(step(after, I('redraft', { actionId: 'A2', body: 'v3' })).r.ok, false, 'placed drafts are not rewritten');
});

test('a permission change between question and yes voids the approval', () => {
  let s = withDraft();
  s = Core.apply(s, { type: 'permissions_set', permissions: s.permissions });
  const { r } = step(s, I('approve'));
  assert.equal(r.ok, false);
  assert.equal(s.pending, null);
});

test('the reducer itself ignores a yes with the wrong recipient or epoch', () => {
  const s = withDraft();
  const p = s.pending;
  for (const e of [{ recipient: 'x@example.com' }, { epoch: p.epoch + 1 }]) {
    const out = Core.apply(s, Object.assign({ type: 'yes', actionId: p.actionId, version: p.version, recipient: p.recipient, epoch: p.epoch }, e));
    assert.equal(out.actions.A2.status, 'drafted', JSON.stringify(e));
    assert.equal(out.log.at(-1).flag, 'ignored');
  }
});

test('link only to a candidate role, and only after Maya confirms the named role', () => {
  let { r, s } = step(live(), I('link', { interviewId: 'I2', oppId: 'O1' }), 'link it to the Halyard one');
  assert.ok(!r.ok && r.clarify, 'a Halyard role is not a Lumen candidate: code asks which, the model id is never used');
  const ask = toEvents(s, I('link', { interviewId: 'I2', oppId: 'O7' }), FX, "it's for the data platform role");
  assert.equal(ask.confirm.question, 'Link the Lumen Data invite to Data Platform Engineer? Reply yes.');
  ({ r, s } = step(s, I('link', { interviewId: 'I2', oppId: 'O7' })));
  assert.equal(r.ok, true);
  assert.equal(s.interviews.I2.oppId, 'O7');
  assert.equal(s.tasks['T-link-I2'].status, 'completed');
  assert.equal(step(s, I('link', { interviewId: 'I2', oppId: 'O5' })).r.ok, false, 'already linked');
});

test('manual done retires the draft and the open question', () => {
  const { r, s } = step(withDraft(), I('manual_done', { taskId: 'T-reply-I2' }));
  assert.equal(r.ok, true);
  assert.equal(s.actions.A2.status, 'retired');
  assert.equal(s.pending, null);
  assert.equal(step(s, I('manual_done', { taskId: 'T-reply-I2' })).r.ok, false);
  for (const taskId of ['T-link-I2', 'T-rec-O8']) assert.equal(step(live(), I('manual_done', { taskId })).r.ok, false, taskId + ' is not a reply task');
});

test('routes: undo, propose only fixture options, choose only the open proposal', () => {
  let { r, s } = step(live(), I('route_choose', { routeId: 'backend-focus' }));
  assert.equal(r.ok, false);
  ({ r, s } = step(s, I('route_undo')));
  assert.equal(r.ok, true);
  assert.equal(s.route.current, FX.defaultRoute);
  assert.equal(step(s, I('route_undo')).r.ok, false, 'nothing left to undo');
  assert.equal(step(s, I('route_propose', { routeId: 'remote-only' })).r.ok, false, 'not a fixture option');
  ({ r, s } = step(s, I('route_propose', { routeId: 'backend-focus' })));
  assert.equal(r.ok, true);
  assert.deepEqual(r.followUp, { intent: { type: 'route_choose', routeId: 'backend-focus' } }, 'the proposal is the question a yes answers');
  ({ r, s } = step(s, I('route_choose', { routeId: 'backend-focus' })));
  assert.equal(s.route.current, '15 a week: backend only');
  ({ s } = step(s, I('route_undo')));
  assert.equal(s.route.current, FX.defaultRoute);
});

test('show_status changes nothing and only names known sections; unknown intents are declined', () => {
  const s = live();
  const { intent, ...ok } = toEvents(s, I('show_status', { section: 'overview' }), FX);
  assert.deepEqual(ok, { ok: true, events: [], card: 'status:overview' });
  assert.equal(toEvents(s, I('show_status', { section: 'everything' }), FX).ok, false);
  assert.equal(toEvents(s, I('send_email'), FX).ok, false);
  assert.equal(toEvents(s, null, FX).ok, false);
  assert.equal(toEvents(s, I('answer', { topic: 'replies' }), FX, 'was I rejected?').ok, true);
  assert.equal(toEvents(s, I('answer', { topic: 'gossip' }), FX, 'x').ok, false);
});

test('consent is never read from free text: consequential intents ask, and only a bare yes applies', () => {
  const s = withDraft();
  // Messages the review found approving, resuming, linking or retiring under keyword gates.
  const notYes = ["I'm not sure", 'Sure, but not now', 'Okay, let me think about it', 'Ok who is it going to?', "I can't approve this",
    'Why would I approve that?', 'no, make it shorter', 'wait', 'yes but change the time', "Don't resume yet", 'What happens if I resume?'];
  for (const text of notYes) {
    assert.equal(isYes(text), false, text);
    assert.equal(local(s, { intent: I('approve') }, text, FX), null, text);
    const r = toEvents(s, I('approve'), FX, text);
    assert.ok(r.confirm && !r.ok, text);
  }
  for (const text of ['yes', 'Yes.', 'ok', 'go ahead', 'yes, put it in my drafts']) assert.equal(isYes(text), true, text);
  for (const [type, text] of [['resume', "Don't resume yet"], ['resume', 'Should I continue with Corvid?'], ['pause', "Don't pause"], ['pause', 'Hold on, what does Priya want?']]) {
    const st = type === 'resume' ? live() : withDraft();
    assert.ok(toEvents(st, I(type), FX, text).confirm, `${type}: ${text}`);
  }
  assert.equal(toEvents(live(), I('resume'), FX, 'ok resume').ok, true, 'bare command applies directly');
  assert.equal(toEvents(withDraft(), I('pause'), FX, 'pause everything for now').ok, true);
  assert.ok(toEvents(withDraft(), I('manual_done', { taskId: 'T-reply-I2' }), FX, "I haven't replied to Priya yet").confirm);
});

test('a yes answers only the question in the latest agent message, re-checked against current state', () => {
  let s = withDraft();
  const draftQ = toEvents(step(live(), I('resume')).s, I('draft', { taskId: 'T-reply-I2', body: 'v1' }), FX, 'x').followUp;
  assert.equal(local(s, draftQ, 'yes', FX).events[1].type, 'placed', 'the draft question');
  assert.equal(local(s, null, 'yes', FX), null, 'no question in the latest message: ask the model, even with a draft open in state');
  const linkQ = { intent: I('link', { interviewId: 'I2', oppId: 'O7' }) };
  assert.equal(local(s, linkQ, 'put it in my drafts', FX), null, 'the drafts phrase is a yes only to the draft question');
  assert.equal(local(s, draftQ, 'put it in my drafts', FX).ok, true);
  const ask = toEvents(s, I('manual_done', { taskId: 'T-reply-I2' }), FX, 'I sent it myself');
  assert.match(ask.confirm.question, /That marks A2 retired in Tsenta's records\. Reply yes\.$/);
  assert.equal(local(s, ask.confirm, 'yes', FX).events[0].type, 'manual_done', 'the confirm wins over the older draft question');
  s = Core.apply(s, { type: 'manual_done', taskId: 'T-reply-I2' });
  assert.equal(local(s, ask.confirm, 'yes', FX).ok, false, 're-checked: already done');
});

test('link: the role comes from Maya naming exactly one candidate, else code asks which; the employer name never names a role', () => {
  const s = step(live(), I('resume')).s;
  const p = I('link', { interviewId: 'I2', oppId: 'O7' });
  const which = 'Which Lumen Data role is the invite for, Backend Engineer or Data Platform Engineer?';
  for (const text of ['Link the Lumen Data invite', "I'm not sure which role", 'not backend, the data platform one']) assert.equal(toEvents(s, p, FX, text).clarify, which, text);
  assert.ok(toEvents(s, p, FX, 'the data platform one').confirm);
  assert.equal(toEvents(s, I('link', { interviewId: 'I2', oppId: '' }), FX, 'the backend one').confirm.intent.oppId, 'O5', 'her words name the role, not the model');
  for (const oppId of ['', 'O9']) assert.equal(toEvents(s, I('link', { interviewId: 'I2', oppId }), FX, 'link it').clarify, which, `model oppId ${JSON.stringify(oppId)}: ask, never decline`);
  // The employer is removed as a phrase, not word by word: "data" alone still names Data Platform.
  for (const text of ['the data one', "it's Lumen's data role", 'Data Platform at Lumen Data']) assert.ok(toEvents(s, p, FX, text).confirm, text);
  assert.equal(toEvents(s, p, FX, 'the one from priya@lumendata.example').clarify, which, 'employer run together in an address');
});

test('the answer to "which role?" is read by code with no model call, then still asks yes', () => {
  const s = step(live(), I('resume')).s;
  const q = toEvents(s, I('link', { interviewId: 'I2', oppId: 'O7' }), FX, 'Link the Lumen Data invite').which;
  assert.deepEqual(q.intent, { type: 'link', interviewId: 'I2' });
  const r = local(s, q, 'the data one', FX);
  assert.equal(r.confirm.question, 'Link the Lumen Data invite to Data Platform Engineer? Reply yes.');
  assert.equal(local(s, q, 'backend', FX).confirm.intent.oppId, 'O5');
  for (const text of ['yes', "I'm not sure", 'Lumen Data', 'backend or data platform, whichever']) assert.equal(local(s, q, text, FX), null, text);
  const linked = local(s, r.confirm, 'yes', FX);
  assert.equal(linked.events[0].oppId, 'O7');
  assert.equal(local(linked.events.reduce(Core.apply, s), q, 'the data one', FX), null, 'already linked: not answered locally');
});

test('negation or doubt never names a role, and her words must agree with a model reading of another role (delta review 2)', () => {
  const s = step(live(), I('resume')).s;
  for (const text of ["it's not the data one", "I'm not sure, could be backend, no idea honestly", "I don't know, not backend", 'either is fine',
    'it isn\u2019t the data one', 'anything except the data one', 'never the data one', 'skip the data one', 'data platform is wrong',
    'anything but the data one', 'drop data platform', 'data platform? no', 'no to data platform', 'rather than data platform', 'data platform is incorrect', 'the data one is a mistake']) {
    assert.ok(toEvents(s, I('link', { interviewId: 'I2', oppId: 'O5' }), FX, text).clarify, text);
    const q = toEvents(s, I('link', { interviewId: 'I2', oppId: '' }), FX, 'link it').which;
    assert.equal(local(s, q, text, FX), null, text);
  }
  assert.ok(toEvents(s, I('link', { interviewId: 'I2', oppId: 'O5' }), FX, 'the data one').clarify, 'model reads Backend, her words say Data Platform: ask');
  // Confident answers name the role (no loop of re-asking).
  for (const [text, id] of [['backend for sure', 'O5'], ['definitely backend', 'O5'], ['no, the data platform one', 'O7'], ['could you link it to backend', 'O5'], ['good idea, data platform', 'O7'], ['link it to data platform, which I applied to in May', 'O7']]) {
    assert.equal(toEvents(s, I('link', { interviewId: 'I2', oppId: '' }), FX, text).confirm.intent.oppId, id, text);
  }
});

test('"the other one" resolves only from context: the other of two candidates after a link yes-question (operator 10:59)', () => {
  const s = step(live(), I('resume')).s;
  const linkQ = toEvents(s, I('link', { interviewId: 'I2', oppId: '' }), FX, 'the backend one').confirm;
  assert.equal(linkQ.intent.oppId, 'O5');
  for (const text of ['no, the other one', 'the other one', 'No the other role', 'other one please']) {
    const r = local(s, linkQ, text, FX);
    assert.equal(r.confirm.intent.oppId, 'O7', text);
    assert.equal(r.confirm.question, 'Link the Lumen Data invite to Data Platform Engineer? Reply yes.');
  }
  const which = toEvents(s, I('link', { interviewId: 'I2', oppId: '' }), FX, 'link it').which;
  assert.equal(local(s, which, 'the other one', FX), null, 'no role was put to her yet: ambiguous, so the model and then code ask');
  assert.equal(local(s, which, 'the other role, backend', FX).confirm.intent.oppId, 'O5', 'a role named outright is not doubt');
  assert.equal(local(s, which, 'other than data platform', FX), null, '"other than" rules a role out');
  assert.equal(local(s, { intent: I('approve') }, 'the other one', FX), null, 'only after a link question');
});

test('while a question is open only the plain commands run locally; synonyms go to the model (delta review 3)', () => {
  const s = step(live(), I('resume')).s;
  const q = { intent: I('approve') };
  for (const text of ['hold', 'stop', 'carry on', 'keep going', 'pause everything for now']) assert.equal(local(s, q, text, FX), null, text);
  assert.equal(local(s, q, 'pause', FX).events[0].type, 'paused');
  assert.equal(local(s, null, 'hold', FX).events[0].type, 'paused', 'no question open: the synonym is a bare command');
});

test('bare commands are answered by code with no model call and checked against state; anything else goes to the model', () => {
  assert.equal(local(live(), null, 'ok resume', FX).events[0].type, 'resumed');
  assert.equal(local(live(), null, 'pause', FX).reason, 'Tsenta is already paused.');
  assert.equal(local(live(), null, 'undo the route change', FX).events[0].type, 'route_undo');
  for (const text of ["Don't resume yet", 'undo that', 'can you pause the Corvid one?', 'what is my status with Halyard?']) assert.equal(local(live(), null, text, FX), null, text);
  for (const [text, section] of [['status', 'overview'], ['Where do things stand?', 'overview'], ['details', 'applications'], ['setup', 'setup']]) {
    const r = local(live(), { intent: I('approve') }, text, FX);
    assert.deepEqual([r.ok, r.events, r.intent.section], [true, [], section], text);
  }
});

test('direct undo needs the word route; a bare "undo that" asks first', () => {
  const s = live();
  assert.ok(toEvents(s, I('route_undo'), FX, 'undo that').confirm);
  assert.equal(toEvents(s, I('route_undo'), FX, 'undo the route change').ok, true);
});

test('model ids are own properties only, and are trimmed once for both the check and the reply', () => {
  let { s } = step(live(), I('resume'));
  for (const [type, f] of [['route_propose', { routeId: 'constructor' }], ['redraft', { actionId: 'constructor', body: 'x' }], ['link', { interviewId: '__proto__', oppId: 'O7' }], ['reconcile', { oppId: 'toString' }]]) {
    assert.equal(toEvents(s, I(type, f), FX, 'x').ok, false, type);
  }
  const r = toEvents(s, I('reconcile', { oppId: 'O8 ' }), FX, 'x');
  assert.equal(r.ok, true);
  assert.equal(r.intent.oppId, 'O8');
});
