const test = require('node:test');
const assert = require('node:assert');
const { initial, apply, replyStatus } = require('../core.js');
const SCENES = require('../scenes.js');

const run = (s, evs) => evs.reduce(apply, s);

const base = () => run(initial(), [
  { type: 'opp_added', id: 'O1', employer: 'Halyard', role: 'ML Platform', receipt: 'confirmed' },
  { type: 'opp_added', id: 'O2', employer: 'Halyard', role: 'Data Infra', receipt: 'attempted' },
  { type: 'invite', id: 'I1', employer: 'Halyard', from: 'jordan@halyard.example', candidates: ['O1', 'O2'] },
  { type: 'draft', actionId: 'A1', taskId: 'T-reply-I1', kind: 'gmail_draft', recipient: 'jordan@halyard.example', body: 'v1' },
]);

test('ambiguous invite is not force-linked', () => {
  const s = base();
  assert.strictEqual(s.interviews.I1.oppId, null);
  assert.strictEqual(s.tasks['T-link-I1'].status, 'awaiting_user');
});

test('yes binds to the asked version, not the newest message', () => {
  let s = run(base(), [
    { type: 'draft', actionId: 'A1', body: 'v2' },
    { type: 'ask_approval', actionId: 'A1' },
    { type: 'message_in', text: 'New match: Northwind' },
    { type: 'yes' },
  ]);
  assert.deepStrictEqual(s.actions.A1.approved, { version: 2, recipient: 'jordan@halyard.example', epoch: 1 });
});

test('yes after a newer draft does not approve the stale question', () => {
  const s = run(base(), [{ type: 'ask_approval', actionId: 'A1' }, { type: 'draft', actionId: 'A1', body: 'v2' }, { type: 'yes' }]);
  assert.strictEqual(s.actions.A1.status, 'drafted');
  assert.strictEqual(s.log.at(-1).flag, 'ignored');
});

test('model intent with the wrong version is ignored', () => {
  const s = run(base(), [{ type: 'ask_approval', actionId: 'A1' }, { type: 'yes', actionId: 'A1', version: 9 }]);
  assert.strictEqual(s.actions.A1.status, 'drafted');
});

test('manual completion retires the stale draft and its timer', () => {
  const s = run(base(), [
    { type: 'ask_approval', actionId: 'A1' }, { type: 'yes' }, { type: 'placed', actionId: 'A1' },
    { type: 'manual_done', taskId: 'T-reply-I1' },
  ]);
  assert.strictEqual(s.actions.A1.status, 'retired');
  assert.strictEqual(s.reminders['R-reply-A1'].status, 'retired');
  assert.strictEqual(s.interviews.I1.status, 'awaiting_employer');
});

test('cancellation retires the reminder and a delayed old confirmation cannot revive it', () => {
  const s = run(base(), [
    { type: 'employer_confirm', interviewId: 'I1', rev: 1, time: 'Thu 2:00 PM' },
    { type: 'employer_cancel', interviewId: 'I1', rev: 2 },
    { type: 'employer_confirm', interviewId: 'I1', rev: 1, time: 'Thu 2:00 PM' },
  ]);
  assert.strictEqual(s.interviews.I1.status, 'cancelled');
  assert.ok(Object.values(s.reminders).every((r) => r.status !== 'active'));
  assert.strictEqual(s.log.at(-1).flag, 'ignored');
});

test('restart turns in-flight work into unknown-effect plus reconcile, never a retry', () => {
  let s = run(base(), [{ type: 'submit_started', oppId: 'O2' }, { type: 'paused' }, { type: 'resumed' }]);
  assert.strictEqual(s.opps.O2.receipt, 'unknown_effect');
  assert.strictEqual(s.tasks['T-rec-O2'].status, 'running');
  s = apply(s, { type: 'reconciled', oppId: 'O2', found: true });
  assert.strictEqual(s.opps.O2.receipt, 'confirmed');
});

test('route choice is reversible', () => {
  let s = run(initial(), [{ type: 'route_propose', from: 'A', to: 'B' }, { type: 'route_choose', to: 'B' }]);
  assert.strictEqual(s.route.current, 'B');
  s = apply(s, { type: 'route_undo' });
  assert.strictEqual(s.route.current, 'A');
});

test('every scripted scene plays end to end through the reducer', () => {
  let s = initial();
  for (const scene of SCENES) for (const step of scene.steps) for (const e of step.ev || []) s = apply(s, e);
  assert.ok(s.log.length > 20);
});

const PERMS = [{ what: 'Put a reply in your Gmail drafts', rule: 'ask' }];
const confirmedCount = (s) => Object.values(s.opps).filter((o) => o.receipt === 'confirmed').length;

test('the same portal confirmation twice is counted once and creates no action or task', () => {
  let s = run(base(), [{ type: 'opp_added', id: 'O3', employer: 'Quill Health', role: 'Backend', receipt: 'queued' },
    { type: 'submit_started', oppId: 'O3' }, { type: 'paused' }, { type: 'resumed' }, { type: 'reconciled', oppId: 'O3', found: true }]);
  const before = { confirmed: confirmedCount(s), opps: Object.keys(s.opps).length, actions: Object.keys(s.actions).length, tasks: Object.keys(s.tasks).length };
  s = run(s, [{ type: 'receipt', oppId: 'O3', receipt: 'confirmed' },
    { type: 'opp_added', id: 'O3', employer: 'Quill Health', role: 'Backend', receipt: 'attempted' }]);
  assert.deepStrictEqual({ confirmed: confirmedCount(s), opps: Object.keys(s.opps).length, actions: Object.keys(s.actions).length, tasks: Object.keys(s.tasks).length }, before);
  assert.strictEqual(s.opps.O3.receipt, 'confirmed'); // a re-ingested older record cannot downgrade it
  assert.deepStrictEqual(s.log.slice(-2).map((l) => l.flag), ['duplicate', 'duplicate']);
});

test('silence with healthy mail is waiting, with a disconnected source is unknown, never rejected', () => {
  let s = run(base(), [
    { type: 'source_status', id: 'gmail', label: 'Gmail job mail', status: 'healthy' },
    { type: 'source_status', id: 'outlook', label: 'School Outlook', status: 'healthy' },
  ]);
  // Variant change (adversarial review finding 1, 2026-10-13): an interview request not yet linked to a role counts as a
  // possible reply for each candidate role, ahead of waiting/unknown. The original waiting/unknown checks below run with
  // the request linked to the other role, so O1 has no candidate request.
  assert.deepStrictEqual(replyStatus(s, 'O1'), { status: 'maybe_replied', why: ['A request from jordan@halyard.example may be about this role (not linked yet)'] });
  const elsewhere = (st) => apply(st, { type: 'link', interviewId: 'I1', oppId: 'O2', evidence: 'test' });
  assert.strictEqual(replyStatus(elsewhere(base()), 'O1').status, 'unknown'); // no mail source connected yet: unknown, not waiting
  assert.strictEqual(replyStatus(elsewhere(s), 'O1').status, 'waiting');
  s = apply(s, { type: 'source_status', id: 'outlook', status: 'disconnected', since: 'Sun 6:10 PM' });
  assert.deepStrictEqual(replyStatus(elsewhere(s), 'O1'), { status: 'unknown', why: ['School Outlook disconnected since Sun 6:10 PM'] });
  assert.strictEqual(replyStatus(s, 'O2').status, 'receipt_attempted');
  assert.strictEqual(replyStatus(apply(s, { type: 'link', interviewId: 'I1', oppId: 'O1', evidence: 'test' }), 'O1').status, 'replied');
  const all = Object.keys(s.opps).map((id) => replyStatus(s, id).status);
  assert.ok(all.every((st) => !/reject/.test(st)), all.join());
  assert.ok(Object.values(s.opps).every((o) => !/reject/.test(o.receipt)));
});

test('a permission change voids the open question; a later yes stays denied', () => {
  const s = run(base(), [{ type: 'ask_approval', actionId: 'A1' }, { type: 'permissions_set', permissions: PERMS }, { type: 'yes' }]);
  assert.strictEqual(s.pending, null);
  assert.strictEqual(s.actions.A1.status, 'drafted');
  assert.deepStrictEqual(s.log.slice(-2).map((l) => l.flag), ['stale', 'ignored']);
});

test('an approval granted under old permissions cannot be placed', () => {
  const s = run(base(), [{ type: 'ask_approval', actionId: 'A1' }, { type: 'yes' },
    { type: 'permissions_set', permissions: PERMS }, { type: 'placed', actionId: 'A1' }]);
  assert.strictEqual(s.actions.A1.status, 'approved');
  assert.strictEqual(s.reminders['R-reply-A1'], undefined);
  assert.strictEqual(s.log.at(-1).flag, 'ignored');
});

test('a changed recipient voids the question; the model cannot approve the old one', () => {
  const s = run(base(), [{ type: 'ask_approval', actionId: 'A1' },
    { type: 'draft', actionId: 'A1', body: 'v2', recipient: 'recruiting@halyard.example' },
    { type: 'yes', actionId: 'A1', version: 1 }, { type: 'yes', actionId: 'A1', version: 2 }]);
  assert.strictEqual(s.actions.A1.status, 'drafted');
  assert.strictEqual(s.actions.A1.recipient, 'recruiting@halyard.example');
  assert.ok(s.log.slice(-2).every((l) => l.flag === 'ignored'));
});
