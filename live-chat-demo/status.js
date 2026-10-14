// Status as a compact text message: plain facts from reducer state, no model text. Text, not an image: a bot in a
// plain iMessage thread can only send messages (no polls or pickers; see specs/002-live-variant/spec.md). The details
// are one more message away ("details", "setup").
// Zero and unknown are kept apart: a count of 0 is a fact; "unknown" always carries its reason.
(function (root) {
  const Core = root.TsentaCore || (typeof require !== 'undefined' ? require('./core.js') : null);
  const RECEIPT = {
    confirmed: 'receipt', attempted: 'attempt only', queued: 'queued, not sent', in_flight: 'mid-submit',
    unknown_effect: 'maybe sent, being checked', not_found: 'no receipt',
  };
  const RULE = { auto: 'on its own', ask: 'asks you first', never: 'never' };
  const SRC = { healthy: 'connected', disconnected: 'disconnected', not_connected: "can't see" };
  const count = (xs, f) => xs.filter(f).length;

  // Three short messages, as a person would text them; reasons and per-application lines are in "details" and "setup".
  const OTHER = { attempted: 'without a receipt', queued: 'queued', in_flight: 'mid\u2011submit', unknown_effect: 'maybe sent, checking', not_found: 'not found' }; // \u2011: no line break inside the word
  function overview(s) {
    const opps = Object.values(s.opps);
    const confirmed = opps.filter((o) => o.receipt === 'confirmed');
    const rs = confirmed.map((o) => Core.replyStatus(s, o.id));
    const down = Object.values(s.sources).filter((x) => ['gmail', 'outlook'].includes(x.id) && x.status !== 'healthy').map((x) => x.label);
    const unlinked = count(Object.values(s.interviews), (iv) => !iv.oppId); // an invite not tied to a role: its replies are only "maybe"
    const open = [];
    if (s.paused) open.push('resume');
    if (s.pending) open.push(`a yes on the draft to ${s.pending.recipient}`);
    for (const t of Object.values(s.tasks)) if (t.status === 'awaiting_user') open.push(t.title.replace(/^Which (.*) role is this invite for\?$/, 'which $1 role').replace(/\?$/, ''));
    const unknown = count(rs, (r) => r.status === 'unknown'), replied = count(rs, (r) => r.status === 'replied'), waiting = count(rs, (r) => r.status === 'waiting');
    return [
      [`${confirmed.length} applied`].concat(Object.keys(OTHER).map((k) => [count(opps, (o) => o.receipt === k), OTHER[k]]).filter(([n]) => n).map(([n, l]) => `${n}\u00a0${l}`)).join(', ') + '.', // a count stays on the line with its label
      [`${replied} ${replied === 1 ? 'reply' : 'replies'}`, unlinked && `${unlinked} invite to link`, waiting && `${waiting} waiting`].filter(Boolean).join(', ').replace(/, ([^,]*)$/, ' and $1') + '.' +
        (unknown ? (down.length ? ` ${down.join(' and ')} ${down.length > 1 ? 'are' : 'is'} down, so ${unknown} ${unknown === 1 ? 'is' : 'are'} unknown.` : ` ${unknown} unknown.`) : ''),
      open.length ? `Needs you: ${open.join(', and ')}.` : 'Nothing needs you right now.',
    ];
  }

  function applications(s) {
    return Object.values(s.opps).map((o) => {
      const r = o.receipt === 'confirmed' ? Core.replyStatus(s, o.id).status : null;
      const reply = !r ? '' : r === 'replied' ? ', replied' : r === 'maybe_replied' ? ', maybe replied (not linked)' : r === 'waiting' ? ', no reply yet' : ', reply unknown';
      return `• ${o.employer}, ${o.role}: ${RECEIPT[o.receipt]}${reply}`;
    });
  }

  function setup(s) {
    return [`• Goal: ${s.goal ? s.goal.text : 'not set'}`]
      .concat(Object.values(s.sources).map((x) => `• ${x.label}: ${SRC[x.status]}${x.since ? ' since ' + x.since : ''}`))
      .concat(s.permissions.map((p) => `• ${p.what}: ${RULE[p.rule]}`));
  }

  const SECTIONS = { overview, applications, setup };
  const TITLES = { overview: 'Where things stand', applications: 'Each application', setup: 'Goal, sources and permissions' };
  const MORE = { applications: 'Say "status" for the summary.', setup: 'Say "status" for the summary.' };

  // clock: the demo's own clock text (e.g. "Tue 10:15 AM"). Built once, from the state at that moment.
  function statusText(state, section, clock) {
    const s = JSON.parse(JSON.stringify(state));
    if (section === 'overview') return overview(s).join('\n\n'); // a blank line starts a new bubble
    return [`${TITLES[section]} · ${clock || 'now'}`].concat(SECTIONS[section](s), ['', MORE[section]]).join('\n');
  }

  const api = { statusText, sections: Object.keys(SECTIONS) };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TsentaStatus = api;
})(this);
