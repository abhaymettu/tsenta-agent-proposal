// Code-owned replies, including the exact overclaims a reviewer found in live model text (2026-10-13 07:30).
const test = require('node:test');
const assert = require('node:assert');
const Core = require('../core.js');
const SCENES = require('../scenes.js');
const FX = require('../fixtures.js');
const { toEvents } = require('../intents.js');
const { say } = require('../voice.js');

const upTo = (n) => { let s = Core.initial(); SCENES.slice(0, n).forEach((sc) => sc.steps.forEach((st) => (st.ev || []).forEach((e) => { s = Core.apply(s, e); }))); return s; };
const reply = (s, intent, text) => { const o = toEvents(s, intent, FX, text); const after = o.ok ? o.events.reduce(Core.apply, s) : s; return say(s, after, intent, o); };
const OVERCLAIM = /\b(nobody|no one|no-one)\b|nothing (has )?come in|pick up where it left off|\bnot rejected\b|\brejected you\b/i;

test('"was I rejected?" says rejections are not tracked, never that none happened; a source down is named', () => {
  const t = reply(upTo(6), { type: 'answer', topic: 'replies' }, 'No reply from Halyard. Was I rejected?');
  assert.doesNotMatch(t, OVERCLAIM);
  assert.match(t, /Tsenta doesn't track rejections, so I can't say whether anyone said no\. I may be missing replies: School Outlook disconnected since Sun 6:10 PM\.$/);
  const healthy = reply(upTo(4), { type: 'answer', topic: 'replies' }, 'was I rejected?');
  assert.match(healthy, /Tsenta doesn't track rejections, so I can't say whether anyone said no\.$/);
  assert.doesNotMatch(healthy, /not a no|waiting, not/);
});

test('an interview request not linked to a role is on record as a possible reply for its candidate roles', () => {
  // Scene 3: Jordan's Halyard request has arrived but is not linked yet.
  const t = reply(upTo(3), { type: 'answer', topic: 'replies', oppId: 'O1' }, 'did Halyard get back to me?');
  assert.match(t, /^Halyard, ML Platform Engineer: maybe replied\. A request from jordan@halyard\.example may be about this role \(not linked yet\)\./);
  assert.doesNotMatch(t, /no reply on record/);
  assert.match(reply(upTo(6), { type: 'answer', topic: 'replies', oppId: 'O7' }, 'lumen?'), /Lumen Data, Data Platform Engineer: maybe replied\. A request from priya@lumendata\.example/);
});

test('one application: attempt-only and disconnected-source cases say unknown, not "nothing came in"', () => {
  const s = upTo(6);
  assert.equal(reply(s, { type: 'answer', topic: 'replies', oppId: 'O2' }, 'what about Halyard?'),
    "Halyard, ML Platform Engineer: they replied (interview cancelled, no new time on record). Halyard, Data Infrastructure Engineer: an attempt with no receipt, so I count it as unknown, not applied. Tsenta doesn't track rejections, so I can't say whether anyone said no. I may be missing replies: School Outlook disconnected since Sun 6:10 PM.");
  assert.match(reply(s, { type: 'answer', topic: 'interviews' }, 'who is Priya?'), /Lumen Data \(role not linked yet\), from priya@lumendata\.example: requested\./);
  assert.match(reply(s, { type: 'answer', topic: 'replies', oppId: 'O4' }, 'northwind?'), /I can't say\. School Outlook disconnected since Sun 6:10 PM/);
});

test('resume after an interrupted submit states uncertain effect, never that it continues', () => {
  const t = reply(upTo(6), { type: 'resume' }, 'ok resume');
  assert.doesNotMatch(t, OVERCLAIM);
  assert.match(t, /may or may not have gone through, so I won't resubmit\. Ask me to check it\./);
});

test('a proposal that points at nothing real gets "not sure", not a confusing decline; state declines stay explicit', () => {
  const s = upTo(6);
  for (const it of [{ type: 'answer', topic: '' }, { type: 'link', interviewId: 'I9', oppId: 'O7' }, { type: 'send_email' }]) {
    assert.match(reply(s, it, 'x'), /^Not sure what you mean\./, JSON.stringify(it));
  }
  assert.equal(reply(s, { type: 'draft', taskId: 'T-reply-I2', body: 'hi' }, 'x'), "That didn't go through: Tsenta is paused. Say resume first.");
});

test('every answer topic renders from state without overclaims', () => {
  const s = upTo(6);
  for (const topic of ['replies', 'receipts', 'interviews', 'open_items', 'sources', 'permissions', 'cannot', 'scope', 'unclear']) {
    const t = reply(s, { type: 'answer', topic }, 'x');
    assert.ok(t.length > 10, topic);
    assert.doesNotMatch(t, OVERCLAIM, topic);
    assert.doesNotMatch(t, /—/, topic);
  }
});
