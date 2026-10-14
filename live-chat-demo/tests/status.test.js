// Status text: facts from state, zero kept apart from unknown, short enough for a phone, and built once.
const test = require('node:test');
const assert = require('node:assert');
const Core = require('../core.js');
const SCENES = require('../scenes.js');
const { statusText } = require('../status.js');

const upTo = (n) => {
  let s = Core.initial();
  SCENES.slice(0, n).forEach((sc) => sc.steps.forEach((st) => (st.ev || []).forEach((e) => { s = Core.apply(s, e); })));
  return s;
};
const line = (t, start) => t.split('\n').find((l) => l.startsWith(start));

test('healthy mail: replies and waiting, no unknown, no claim about rejections', () => {
  const t = statusText(upTo(4), 'overview', 'Sat 7:12 AM');
  assert.equal(t.split('\n\n')[1], '1 reply and 4 waiting.');
  assert.doesNotMatch(t, /reject/i);
});

test('a disconnected source turns silence into unknown, with the reason, not into zero', () => {
  const t = statusText(upTo(5), 'overview', 'Mon 9:30 AM');
  assert.equal(t.split('\n\n')[1], '1 reply. School Outlook is down, so 4 are unknown.');
  assert.match(statusText(upTo(5), 'setup', 'Mon 9:30 AM'), /• School Outlook: disconnected since Sun 6:10 PM/, 'the reason in full is one message away');
});

test('scene 6 overview: three short messages, no bullets or headers', () => {
  const t = statusText(upTo(6), 'overview', 'Tue 10:15 AM');
  assert.deepEqual(t.split('\n\n'), [
    '6 applied, 1\u00a0without a receipt, 1\u00a0mid\u2011submit.',
    '1 reply and 1 invite to link. School Outlook is down, so 3 are unknown.',
    'Needs you: resume, and which Lumen Data role.',
  ]);
  assert.ok(t.split('\n\n').every((l) => l.length <= 80 && !l.includes('\n') && !l.startsWith('•')), 'each a short single message');
});

test('details and setup list every application and every rule', () => {
  const apps = statusText(upTo(6), 'applications', 'Tue 10:15 AM').split('\n');
  assert.equal(apps.filter((l) => l.startsWith('• ')).length, 8);
  assert.ok(apps.includes('• Corvid Systems, Backend Engineer: mid-submit'));
  assert.ok(apps.includes('• Halyard, Data Infrastructure Engineer: attempt only'));
  const setup = statusText(upTo(6), 'setup', 'Tue 10:15 AM');
  assert.match(setup, /• Send anything from your account: never/);
  assert.match(setup, /• School Outlook: disconnected since Sun 6:10 PM/);
});

test('the text is built once: later state does not change it', () => {
  let s = upTo(6);
  const t = statusText(s, 'overview', 'Tue 10:15 AM');
  s = Core.apply(s, { type: 'resumed' });
  assert.match(t, /Needs you: resume/);
  assert.doesNotMatch(t, /—/);
});
