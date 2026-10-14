// Maps one model-proposed intent to reducer events, or declines it with a plain reason.
// The model only proposes. Recipients, ids, evidence and routes come from state and fixtures, never from model text.
// Pure: toEvents(state, intent, fixtures, userText) -> { ok: true, events, card } | { ok: false, reason }.
// Consequential intents are confirmed with Maya by a code-written question before they apply (see CONSENT).
(function (root) {
  const OPEN_TASK = ['accepted', 'awaiting_user', 'running'];
  const no = (reason) => ({ ok: false, reason });
  // The proposal points at nothing real (a model mistake, not something Maya tried): the reply is a plain "not sure".
  const bad = (reason) => ({ ok: false, reason, invalid: true });
  const yes = (events, card) => ({ ok: true, events, card: card || null });
  const str = (x) => (typeof x === 'string' ? x.trim() : '');
  const TOPICS = ['replies', 'receipts', 'interviews', 'open_items', 'sources', 'permissions', 'cannot', 'scope', 'unclear'];
  // Own properties only: a model id like "constructor" must not reach a built-in.
  const own = (o, k) => (o && typeof k === 'string' && Object.prototype.hasOwnProperty.call(o, k) ? o[k] : undefined);
  // Consent is never read from free text. A consequential intent gets a code-written question, and only a short
  // whole-message yes (handled locally by `local`, no model call) applies it. Pause, resume and undo also apply
  // directly when the whole message is the bare command.
  const CONSENT = ['approve', 'link', 'manual_done', 'pause', 'resume', 'route_choose', 'route_undo'];
  const DIRECT = {
    pause: /^(please )?(pause|stop|hold)( (it|everything|tsenta|all))?( for now)?( please)?[.!]*$/i,
    resume: /^((ok|okay|yes),? )?(resume|unpause|start again|carry on|keep going)( (it|everything|tsenta))?( now)?( please)?[.!]*$/i,
    route_undo: /^(please )?(undo|revert) the route( change)?( please)?[.!]*$/i, // a bare "undo" could mean anything just shown
  };
  // While a question is open, only the plain words run locally: a synonym like "hold" or "carry on" may be her answer
  // to that question, so it goes to the model, which sees the question.
  const PLAIN = /^(please )?(pause|resume|undo the route)( please)?[.!]*$/i;
  // Negation or doubt: matching role words would put to her the role she just ruled out ("not the data one").
  // Confident answers with "no," or "for sure" still name a role; "no idea" and "could be" are doubt.
  // A leading "no," is a correction ("no, the data platform one"); "no" anywhere else ("data platform? no") is doubt.
  const DOUBT = /\b(not|never|neither|nor|except|but|rather|skip|drop|wrong|incorrect|mistake|without|other than(?! that)|either|both|unsure|maybe|might|perhaps|whichever|no idea|no to|could be)\b|n't\b|(?<!^)\bno\b/i;
  // Exact status words need no model: they change nothing and are answered from state.
  const SHOW = { overview: /^(status|where do things stand\??|where are we\??)$/i, applications: /^details$/i, setup: /^setup$/i };
  // "the other one" after a link yes-question: the other of exactly two candidates. Without that context it is ambiguous.
  const OTHER = /^(no,? )?(the )?other( one| role)?( please)?[.!]*$/i;
  const YES = [
    /^(yes|yep|yeah|yup|y|ok|okay|sure|confirm|confirmed|do it|go ahead|yes please|please do|sounds good|looks good)[.!]*$/i,
    /^((yes|ok|okay|sure),? )?(put|add) (it|that) in(to)? (my )?(gmail )?drafts( please)?[.!]*$/i,
  ];
  const isYes = (text) => YES.some((r) => r.test(String(text || '').trim()));
  // The drafts phrase is a yes only to the draft question.
  const yesTo = (question, text) => YES[0].test(String(text || '').trim()) || (question.intent.type === 'approve' && YES[1].test(String(text || '').trim()));

  function nextActionId(s) {
    let n = 1;
    while (s.actions['A' + n]) n++;
    return 'A' + n;
  }

  const rules = {
    answer(s, it) {
      if (!TOPICS.includes(it.topic)) return bad('That is not something I can answer here.');
      if (it.oppId && !own(s.opps, it.oppId)) return bad('There is no application with that id.');
      return yes([]);
    },
    pause: (s) => (s.paused ? no('Tsenta is already paused.') : yes([{ type: 'paused' }])),
    resume: (s) => (!s.paused ? no("Tsenta isn't paused.") : yes([{ type: 'resumed' }])),

    draft(s, it) {
      if (s.paused) return no('Tsenta is paused. Say resume first.');
      const t = own(s.tasks, it.taskId);
      if (!t || !t.interviewId || !OPEN_TASK.includes(t.status)) return bad('There is no open reply to draft for that.');
      const live = Object.values(s.actions).find((a) => a.taskId === t.id && !['retired'].includes(a.status));
      if (live) return live.status === 'placed' ? no(`${live.id} is already in your Gmail drafts (simulated).`) : no(`${live.id} already exists; ask for a new version of it instead.`);
      const body = str(it.body);
      if (!body || body.length > 700) return no('The draft text was empty or too long.');
      const id = nextActionId(s);
      const recipient = s.interviews[t.interviewId].from; // set by code from the invite, never by the model
      return yes([
        { type: 'draft', actionId: id, taskId: t.id, kind: 'gmail_draft', recipient, body, by: 'claude' },
        { type: 'ask_approval', actionId: id },
      ], 'draft:' + id);
    },

    redraft(s, it) {
      if (s.paused) return no('Tsenta is paused. Say resume first.');
      const a = own(s.actions, it.actionId);
      if (!a) return bad('There is no draft with that id.');
      if (a.status === 'placed') return no(`${a.id} is already in your Gmail drafts (simulated).`);
      if (a.status === 'retired') return no(`${a.id} was retired${a.why ? ' (' + a.why + ')' : ''}.`);
      const body = str(it.body);
      if (!body || body.length > 700) return no('The draft text was empty or too long.');
      return yes([{ type: 'draft', actionId: a.id, body, by: 'claude' }, { type: 'ask_approval', actionId: a.id }], 'draft:' + a.id);
    },

    // Built from the open question in state; the model's copy of its fields is never used.
    approve(s) {
      if (s.paused) return no('Tsenta is paused. Say resume first.');
      const p = s.pending;
      if (!p) return no('There is no open question to say yes to.');
      return yes([
        { type: 'yes', actionId: p.actionId, version: p.version, recipient: p.recipient, epoch: p.epoch },
        { type: 'placed', actionId: p.actionId },
      ], 'approved:' + p.actionId);
    },

    reconcile(s, it, fx) {
      const o = own(s.opps, it.oppId);
      if (!o) return bad('There is no application with that id.');
      if (o.receipt === 'in_flight') return no(`${o.employer} is still marked mid-submit. Resume first, then it can be checked.`);
      if (o.receipt !== 'unknown_effect') return no(`${o.employer} is not waiting on a check (it is ${o.receipt.replace('_', ' ')}).`);
      const ev = own(fx.evidence, o.id);
      if (!ev) return no(`There is no portal evidence on file for ${o.employer}, so it stays unknown.`);
      return yes([{ type: 'reconciled', oppId: o.id, found: ev.found, evidence: ev.source }], 'receipts');
    },

    link(s, it, fx) {
      const iv = own(s.interviews, it.interviewId);
      if (!iv) return bad('There is no interview request with that id.');
      if (iv.oppId) return no(`That request is already linked to ${s.opps[iv.oppId].role}.`);
      if (!iv.candidates.includes(it.oppId)) return no(`That role is not one of the ${iv.employer} roles this request could be for.`);
      return yes([{ type: 'link', interviewId: iv.id, oppId: it.oppId, evidence: fx.candidateEvidence }], 'invite:' + iv.id);
    },

    // Only a reply task: Maya handling a link or receipt check herself would leave state claiming things it can't know.
    manual_done(s, it) {
      const t = own(s.tasks, it.taskId);
      if (!t || !t.interviewId || !t.id.startsWith('T-reply-')) return bad('Only a reply you sent yourself can be marked done here.');
      if (!OPEN_TASK.includes(t.status)) return no(`"${t.title}" is already ${t.status}.`);
      return yes([{ type: 'manual_done', taskId: t.id }]);
    },

    route_propose(s, it, fx) {
      const r = own(fx.routes, it.routeId);
      if (!r) return bad('That is not one of the route options on file.');
      const current = s.route ? s.route.current : fx.defaultRoute;
      if (current === r.to) return no('That is already the current route.');
      return yes([{ type: 'route_propose', from: current, to: r.to, why: r.why }], 'route');
    },

    route_choose(s, it, fx) {
      const r = own(fx.routes, it.routeId);
      if (!r || !s.route || s.route.proposed !== r.to) return no('There is no open route proposal matching that.');
      return yes([{ type: 'route_choose', to: r.to }]);
    },

    route_undo: (s) => (s.route && s.route.previous ? yes([{ type: 'route_undo' }]) : no('There is no route change to undo.')),

    show_status: (s, it) => (['overview', 'applications', 'setup'].includes(it.section) ? yes([], 'status:' + str(it.section)) : bad('Unknown status section.')),
  };

  // The question code asks before a consequential intent applies. Facts come from state, never from the model.
  const QUESTION = {
    approve: (s) => `Put v${s.pending.version} to ${s.pending.recipient} in your Gmail drafts? Reply yes. You send it, not me.`,
    link: (s, it) => `Link the ${s.interviews[it.interviewId].employer} invite to ${s.opps[it.oppId].role}? Reply yes.`,
    manual_done: (s, it) => {
      const acts = Object.values(s.actions).filter((a) => a.taskId === it.taskId);
      const fx = acts.filter((a) => !['retired', 'done'].includes(a.status)).map((a) => ` That marks ${a.id} retired in Tsenta's records.`).join('');
      return `Mark "${s.tasks[it.taskId].title}" as handled by you?${fx} Reply yes.`;
    },
    pause: () => 'Pause Tsenta? Nothing new starts until you resume. Reply yes.',
    resume: (s) => 'Resume Tsenta?' + Object.values(s.opps).filter((o) => o.receipt === 'in_flight').map((o) => ` ${o.employer} was mid-submit; nothing is retried, and you can ask me to check it.`).join('') + ' Reply yes.',
    route_choose: (s, it, fx) => `Switch to ${fx.routes[it.routeId].to}? Reply yes. It can be undone.`,
    route_undo: (s) => `Undo the route change, back to ${s.route.previous}? Reply yes.`,
  };

  const normalize = (intent) => {
    const it = {};
    for (const [k, v] of Object.entries(intent || {})) it[k] = typeof v === 'string' ? v.trim() : v;
    return it;
  };

  // Which candidate roles Maya's own words name. The employer's name is removed as a whole phrase (also run together, as
  // in an address), so "Lumen Data" never names "Data Platform" while "the data one" still does.
  function namedRoles(s, iv, text) {
    if (DOUBT.test(String(text || '').replace(/[\u2018\u2019]/g, "'"))) return []; // code asks which instead (iOS types curly apostrophes)
    const emp = new RegExp('\\b' + iv.employer.toLowerCase().split(/\W+/).filter(Boolean).join('\\W*') + '\\b', 'g');
    const t = String(text || '').toLowerCase().replace(emp, ' ').split(/\W+/).filter(Boolean);
    const words = (id) => s.opps[id].role.toLowerCase().split(/\W+/).filter(Boolean);
    return iv.candidates.filter((id) => {
      const others = new Set(iv.candidates.filter((c) => c !== id).flatMap(words));
      return words(id).some((w) => !others.has(w) && t.includes(w));
    });
  }

  // A model proposal for Maya's message. Consequential intents come back as { ok: false, confirm } unless the whole
  // message is a bare direct command. Accepted draft and route proposals carry `followUp`: the question they ask.
  function toEvents(state, intent, fixtures, userText) {
    if (!intent) return no('No proposal came back.');
    const it = normalize(intent);
    const rule = own(rules, it.type);
    if (!rule) return Object.assign(bad(`"${it.type}" is not something this agent can do.`), { intent: it });
    if (it.type === 'link') { // the role comes from Maya's words, never the model's guess: exactly one named role, or code asks which
      const iv = own(state.interviews, it.interviewId);
      if (iv && !iv.oppId) {
        const named = namedRoles(state, iv, userText);
        if (named.length !== 1 || (iv.candidates.includes(it.oppId) && it.oppId !== named[0])) { // her words name one role, and the model doesn't read another
          const clarify = `Which ${iv.employer} role is the invite for, ${iv.candidates.map((id) => state.opps[id].role).join(' or ')}?`;
          return { ok: false, clarify, which: { intent: { type: 'link', interviewId: iv.id }, question: clarify }, intent: it }; // `which`: her answer is read locally
        }
        it.oppId = named[0];
      }
    }
    const r = Object.assign(rule(state, it, fixtures), { intent: it });
    if (r.ok && (it.type === 'draft' || it.type === 'redraft')) r.followUp = { intent: { type: 'approve' } };
    if (r.ok && it.type === 'route_propose') r.followUp = { intent: { type: 'route_choose', routeId: it.routeId } };
    if (!r.ok || !CONSENT.includes(it.type)) return r;
    const direct = DIRECT[it.type] && DIRECT[it.type].test(String(userText || '').trim());
    return direct ? r : { ok: false, confirm: { intent: it, question: QUESTION[it.type](state, it, fixtures) }, intent: it };
  }

  // Before any model call, code answers three kinds of message itself, with no model call:
  // - an answer naming exactly one role, to the "which role?" question in the agent's latest message (then asks yes);
  // - a whole-message yes to the question code asked in the agent's latest message (`question`, dropped by the app on
  //   any later message or scripted step), re-checked against current state. Nothing else open in state is answered;
  // - a bare direct command (pause, resume, "undo the route"), checked against state like any proposal.
  // Returns null to ask the model instead.
  function local(state, question, userText, fixtures) {
    const text = String(userText || '').trim();
    if (question && question.intent.type === 'link' && !question.intent.oppId) {
      const iv = own(state.interviews, question.intent.interviewId);
      const named = iv && !iv.oppId && text.length <= 60 ? namedRoles(state, iv, text) : [];
      if (named.length === 1) return toEvents(state, { type: 'link', interviewId: iv.id, oppId: named[0] }, fixtures, text);
    } else if (question && question.intent.type === 'link' && OTHER.test(text)) {
      const iv = own(state.interviews, question.intent.interviewId);
      if (iv && !iv.oppId && iv.candidates.length === 2 && iv.candidates.includes(question.intent.oppId)) {
        const it = { type: 'link', interviewId: iv.id, oppId: iv.candidates.find((c) => c !== question.intent.oppId) };
        return { ok: false, confirm: { intent: it, question: QUESTION.link(state, it) }, intent: it };
      }
    } else if (question && yesTo(question, text)) return Object.assign(rules[question.intent.type](state, question.intent, fixtures), { intent: question.intent });
    const type = Object.keys(DIRECT).find((k) => DIRECT[k].test(text) && (!question || PLAIN.test(text)));
    if (type) return Object.assign(rules[type](state, { type }, fixtures), { intent: { type } });
    const section = Object.keys(SHOW).find((k) => SHOW[k].test(text));
    return section ? Object.assign(rules.show_status(state, { section }), { intent: { type: 'show_status', section } }) : null;
  }

  const api = { toEvents, local, isYes, types: Object.keys(rules), topics: TOPICS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TsentaIntents = api;
})(this);
