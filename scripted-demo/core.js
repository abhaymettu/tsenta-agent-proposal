// Deterministic state core. The model (or the script) proposes events; this reducer decides.
// Pure: apply(state, event) returns a new state and never mutates its input.
(function (root) {
  const clone = (x) => JSON.parse(JSON.stringify(x));

  function initial() {
    return {
      epoch: 1, // permission epoch: bumps when grants change
      paused: false,
      goal: null,
      permissions: [],
      sources: {},
      opps: {},
      interviews: {},
      tasks: {},
      actions: {},
      reminders: {},
      pending: null, // the one action a "yes" can approve right now
      route: null,
      log: [],
    };
  }

  function note(s, type, text, extra) {
    s.log.push(Object.assign({ seq: s.log.length + 1, type, text }, extra || {}));
  }

  function retireTaskWork(s, taskId, why) {
    for (const a of Object.values(s.actions)) {
      if (a.taskId === taskId && !['retired', 'done'].includes(a.status)) {
        a.status = 'retired';
        a.why = why;
        if (s.pending && s.pending.actionId === a.id) s.pending = null;
      }
    }
    for (const r of Object.values(s.reminders)) {
      if (r.taskId === taskId && r.status === 'active') { r.status = 'retired'; r.why = why; }
    }
  }

  const handlers = {
    goal_set(s, e) {
      s.goal = { text: e.text, constraints: e.constraints || [] };
      note(s, e.type, 'Goal recorded');
    },
    permissions_set(s, e) {
      s.permissions = e.permissions;
      s.epoch += 1;
      note(s, e.type, `Permissions set (epoch ${s.epoch})`);
      // An approval question asked under the old grants is void; it must be asked again.
      if (s.pending) { note(s, e.type, `Open question on ${s.pending.actionId} voided by the permission change`, { flag: 'stale' }); s.pending = null; }
    },
    source_status(s, e) {
      s.sources[e.id] = { id: e.id, label: e.label || (s.sources[e.id] || {}).label, status: e.status, since: e.since || null };
      note(s, e.type, `${s.sources[e.id].label}: ${e.status}`);
    },
    opp_added(s, e) {
      if (s.opps[e.id]) { note(s, e.type, `${e.employer}, ${e.role}: already tracked, not added twice`, { flag: 'duplicate' }); return; }
      s.opps[e.id] = { id: e.id, employer: e.employer, role: e.role, receipt: e.receipt || 'confirmed', applied: e.applied || null };
      note(s, e.type, `${e.employer}, ${e.role}: ${s.opps[e.id].receipt}`);
    },
    submit_started(s, e) {
      s.opps[e.oppId].receipt = 'in_flight';
      note(s, e.type, `Submitting ${s.opps[e.oppId].employer}`);
    },
    paused(s, e) {
      s.paused = true;
      note(s, e.type, 'Paused by candidate');
    },
    resumed(s, e) {
      s.paused = false;
      // Recovery: anything that was mid-flight may or may not have happened. Never replay blindly.
      for (const o of Object.values(s.opps)) {
        if (o.receipt === 'in_flight') {
          o.receipt = 'unknown_effect';
          s.tasks['T-rec-' + o.id] = { id: 'T-rec-' + o.id, title: `Reconcile ${o.employer} submit`, status: 'running', oppId: o.id };
          note(s, e.type, `${o.employer}: possible effect, reconcile before any retry`, { flag: 'recovery' });
        }
      }
      note(s, e.type, 'Resumed');
    },
    reconciled(s, e) {
      const o = s.opps[e.oppId];
      o.receipt = e.found ? 'confirmed' : 'not_found';
      const t = s.tasks['T-rec-' + o.id];
      if (t) t.status = 'completed';
      note(s, e.type, `${o.employer}: ${e.found ? 'receipt found, no retry needed' : 'no receipt, retry needs approval'}`);
    },
    receipt(s, e) {
      if (s.opps[e.oppId].receipt === e.receipt) { note(s, e.type, `${s.opps[e.oppId].employer}: same ${e.receipt} receipt again, counted once`, { flag: 'duplicate' }); return; }
      s.opps[e.oppId].receipt = e.receipt;
      note(s, e.type, `${s.opps[e.oppId].employer}, ${s.opps[e.oppId].role}: ${e.receipt}`);
    },
    invite(s, e) {
      // Link only when exactly one opportunity fits. Ambiguity becomes a question, not a guess.
      const linked = e.candidates.length === 1 ? e.candidates[0] : null;
      s.interviews[e.id] = { id: e.id, employer: e.employer, from: e.from, oppId: linked, candidates: e.candidates, status: 'requested', rev: 0, time: null };
      if (!linked) {
        s.tasks['T-link-' + e.id] = { id: 'T-link-' + e.id, title: `Which ${e.employer} role is this invite for?`, status: 'awaiting_user' };
      }
      s.tasks['T-reply-' + e.id] = { id: 'T-reply-' + e.id, title: `Reply to ${e.from}`, status: 'accepted', interviewId: e.id };
      note(s, e.type, linked ? 'Invite linked' : `Invite unlinked: ${e.candidates.length} possible roles`);
    },
    link(s, e) {
      s.interviews[e.interviewId].oppId = e.oppId;
      const t = s.tasks['T-link-' + e.interviewId];
      if (t) t.status = 'completed';
      note(s, e.type, `Invite linked to ${s.opps[e.oppId].role} (${e.evidence})`);
    },
    draft(s, e) {
      const a = s.actions[e.actionId] || { id: e.actionId, kind: e.kind, taskId: e.taskId, recipient: e.recipient, versions: [], status: 'drafted' };
      a.versions.push({ v: a.versions.length + 1, body: e.body });
      if (e.recipient) a.recipient = e.recipient;
      a.status = 'drafted';
      s.actions[a.id] = a;
      // A new version invalidates any approval question about the old one.
      if (s.pending && s.pending.actionId === a.id) s.pending = null;
      note(s, e.type, `${a.id} v${a.versions.length} drafted`);
    },
    ask_approval(s, e) {
      const a = s.actions[e.actionId];
      s.pending = { actionId: a.id, version: a.versions.length, recipient: a.recipient };
      note(s, e.type, `Asked: approve ${a.id} v${s.pending.version} to ${a.recipient}`);
    },
    message_in(s, e) {
      // Unrelated inbound messages never move the approval target.
      note(s, e.type, e.text);
    },
    yes(s, e) {
      const p = s.pending;
      const a = p && s.actions[p.actionId];
      if (!p || !a || a.versions.length !== p.version || a.recipient !== p.recipient) {
        note(s, e.type, '"yes" ignored: nothing exact to approve', { flag: 'ignored' });
        return;
      }
      if (e.actionId && (e.actionId !== p.actionId || e.version !== p.version)) {
        note(s, e.type, '"yes" ignored: proposal did not match the open question', { flag: 'ignored' });
        return;
      }
      a.status = 'approved';
      a.approved = { version: p.version, recipient: p.recipient, epoch: s.epoch };
      s.pending = null;
      note(s, e.type, `Approved ${a.id} v${p.version} to ${p.recipient}`);
    },
    placed(s, e) {
      const a = s.actions[e.actionId];
      if (a.status !== 'approved') { note(s, e.type, `${a.id} not approved; nothing placed`, { flag: 'ignored' }); return; }
      if (a.approved.epoch !== s.epoch) { note(s, e.type, `${a.id} approved under old permissions (epoch ${a.approved.epoch}); nothing placed`, { flag: 'ignored' }); return; }
      a.status = 'placed';
      s.reminders['R-reply-' + a.id] = { id: 'R-reply-' + a.id, taskId: a.taskId, label: 'Nudge if no reply in 3 days', status: 'active' };
      note(s, e.type, `${a.id} v${a.approved.version} placed in Gmail drafts (candidate sends)`);
    },
    manual_done(s, e) {
      const t = s.tasks[e.taskId];
      t.status = 'completed';
      t.by = 'candidate';
      retireTaskWork(s, e.taskId, 'candidate handled it');
      if (t.interviewId) s.interviews[t.interviewId].status = 'awaiting_employer';
      note(s, e.type, `${t.title}: done by candidate; stale draft and timer retired`);
    },
    employer_confirm(s, e) {
      const iv = s.interviews[e.interviewId];
      if (e.rev <= iv.rev) { note(s, e.type, `Late confirmation rev ${e.rev} ignored (current rev ${iv.rev}, ${iv.status})`, { flag: 'ignored' }); return; }
      iv.status = 'confirmed'; iv.rev = e.rev; iv.time = e.time;
      for (const r of Object.values(s.reminders)) if (r.interviewId === iv.id && r.status === 'active') r.status = 'retired';
      s.reminders['R-iv-' + e.rev] = { id: 'R-iv-' + e.rev, interviewId: iv.id, label: `Prep + reminder, ${e.time}`, status: 'active', rev: e.rev };
      note(s, e.type, `Interview confirmed rev ${e.rev}: ${e.time}`);
    },
    employer_cancel(s, e) {
      const iv = s.interviews[e.interviewId];
      if (e.rev <= iv.rev) { note(s, e.type, `Late cancel rev ${e.rev} ignored`, { flag: 'ignored' }); return; }
      iv.status = 'cancelled'; iv.rev = e.rev; iv.time = null;
      for (const r of Object.values(s.reminders)) if (r.interviewId === iv.id && r.status === 'active') { r.status = 'retired'; r.why = 'cancelled'; }
      note(s, e.type, `Interview cancelled rev ${e.rev}; reminders retired`);
    },
    route_propose(s, e) {
      s.route = { current: e.from, proposed: e.to, previous: null, why: e.why };
      note(s, e.type, `Proposed: ${e.to}`);
    },
    route_choose(s, e) {
      if (!s.route || s.route.proposed !== e.to) { note(s, e.type, 'Choice ignored: not the open proposal', { flag: 'ignored' }); return; }
      s.route = { current: e.to, proposed: null, previous: s.route.current };
      note(s, e.type, `Route changed (reversible): ${e.to}`);
    },
    route_undo(s, e) {
      if (!s.route || !s.route.previous) { note(s, e.type, 'Nothing to undo', { flag: 'ignored' }); return; }
      s.route = { current: s.route.previous, proposed: null, previous: null };
      note(s, e.type, 'Route change undone');
    },
  };

  // What silence on an application means. Derived from state only; never "rejected" without the employer saying so.
  const MAIL = ['gmail', 'outlook'];
  function replyStatus(s, oppId) {
    const o = s.opps[oppId];
    if (o.receipt !== 'confirmed') return { status: 'receipt_' + o.receipt };
    if (Object.values(s.interviews).some((iv) => iv.oppId === oppId)) return { status: 'replied' };
    const down = MAIL.map((id) => s.sources[id] || { label: id, status: 'not_connected' }).filter((src) => src.status !== 'healthy');
    if (down.length) return { status: 'unknown', why: down.map((src) => `${src.label} ${src.status}${src.since ? ' since ' + src.since : ''}`) };
    return { status: 'waiting', why: ['all mail sources healthy; no reply yet'] };
  }

  function apply(state, event) {
    const h = handlers[event.type];
    if (!h) throw new Error('unknown event ' + event.type);
    const s = clone(state);
    h(s, event);
    return s;
  }

  const api = { initial, apply, replyStatus, types: Object.keys(handlers) };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TsentaCore = api;
})(this);
