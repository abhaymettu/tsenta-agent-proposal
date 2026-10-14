// Code-owned replies. The model never writes what the agent says: it picks an intent (or an answer topic), and
// these templates state only what reducer state shows. Absence is phrased as "on record", never as fact about the world.
(function (root) {
  const Core = root.TsentaCore || (typeof require !== 'undefined' ? require('./core.js') : null);
  const Status = root.TsentaStatus || (typeof require !== 'undefined' ? require('./status.js') : null);
  const RECEIPT = { attempted: 'an attempt with no receipt', queued: 'queued, not sent', in_flight: 'mid-submit', unknown_effect: 'maybe sent, being checked', not_found: 'no receipt found' };

  const down = (s) => Object.values(s.sources).filter((x) => ['gmail', 'outlook'].includes(x.id) && x.status !== 'healthy');
  const downText = (s) => down(s).map((x) => `${x.label} ${x.status}${x.since ? ' since ' + x.since : ''}`).join('; ');
  const who = (o) => `${o.employer}, ${o.role}`;

  function oneReply(s, o) {
    if (o.receipt !== 'confirmed') return `${who(o)}: ${RECEIPT[o.receipt]}, so I count it as unknown, not applied.`;
    const r = Core.replyStatus(s, o.id);
    if (r.status === 'replied') { // what became of the reply matters more than that it exists ("they replied" alone hid a cancellation)
      const iv = Object.values(s.interviews).find((x) => x.oppId === o.id);
      return `${who(o)}: they replied (interview ${Core.interviewText(iv)}).`;
    }
    if (r.status === 'maybe_replied') return `${who(o)}: maybe replied. ${r.why.join('; ')}.`;
    if (r.status === 'waiting') return `${who(o)}: no reply on record yet, and mail is connected.`;
    return `${who(o)}: I can't say. ${r.why.join('; ')}, so a reply could be there without me seeing it.`;
  }

  // Tsenta has no rejection event in this demo, so it can say nothing either way about a no.
  const rejection = (s, saidDown) => " Tsenta doesn't track rejections, so I can't say whether anyone said no." + (down(s).length && !saidDown ? ` I may be missing replies: ${downText(s)}.` : '');

  function replies(s, oppId) {
    // Asked about one application: answer for every application at that employer, so a second role is never left out.
    if (oppId && Object.prototype.hasOwnProperty.call(s.opps, oppId)) {
      const rows = Object.values(s.opps).filter((o) => o.employer === s.opps[oppId].employer).map((o) => oneReply(s, o));
      return rows.join(' ') + rejection(s, rows.some((r) => r.includes("I can't say.")));
    }
    const rs = Object.values(s.opps).filter((o) => o.receipt === 'confirmed').map((o) => Core.replyStatus(s, o.id).status);
    const n = (k) => rs.filter((x) => x === k).length;
    const maybe = n('maybe_replied') ? `, ${n('maybe_replied')} possibly replied (an interview request not linked to a role yet)` : '';
    return `On record: ${n('replied')} replied${maybe}, ${n('waiting')} with no reply yet, ${n('unknown')} unknown.` + rejection(s);
  }

  const ANSWERS = {
    replies,
    receipts(s) {
      const os = Object.values(s.opps);
      const not = os.filter((o) => o.receipt !== 'confirmed');
      return `Confirmed with a receipt: ${os.length - not.length}.` + (not.length ? ' Not confirmed: ' + not.map((o) => `${who(o)} (${RECEIPT[o.receipt]})`).join('; ') + '.' : '');
    },
    interviews(s) {
      const ivs = Object.values(s.interviews);
      if (!ivs.length) return 'No interview requests on record.';
      return ivs.map((iv) => `${iv.employer}${iv.oppId ? ', ' + s.opps[iv.oppId].role : ' (role not linked yet)'}, from ${iv.from}: ${Core.interviewText(iv)}.`).join(' ');
    },
    open_items(s) {
      const items = [];
      if (s.paused) items.push('Tsenta is paused');
      if (s.pending) items.push(`your yes on ${s.pending.actionId} v${s.pending.version} to ${s.pending.recipient}`);
      for (const t of Object.values(s.tasks)) if (t.status === 'awaiting_user') items.push(t.title.replace(/\?$/, ''));
      return items.length ? 'Waiting on you: ' + items.join('; ') + '.' : 'Nothing is waiting on you right now.';
    },
    sources(s) {
      return Object.values(s.sources).map((x) => `${x.label}: ${x.status === 'healthy' ? 'connected' : x.status === 'not_connected' ? "can't see" : x.status}${x.since ? ' since ' + x.since : ''}`).join('. ') + '.';
    },
    permissions(s) {
      const R = { auto: 'on its own', ask: 'asks you first', never: 'never' };
      return s.permissions.map((p) => `${p.what}: ${R[p.rule]}`).join('. ') + '.';
    },
    cannot: () => "I never send anything from your account, and I never accept or decline an interview time. I can draft it for you to send.",
    scope: () => 'This demo only covers your job search.',
    unclear: () => "Not sure what you mean. I can give you a status, draft a reply, pause or resume, or check an application.",
  };

  // before/after: state around the accepted events; clock: the demo clock for status text. Returns the agent's message text.
  function say(before, after, intent, outcome, clock) {
    if (outcome.confirm) return outcome.confirm.question;
    if (outcome.clarify) return outcome.clarify;
    if (outcome.invalid) return ANSWERS.unclear();
    if (!outcome.ok) return `That didn't go through: ${outcome.reason}`;
    intent = outcome.intent || intent; // the normalized intent intents.js checked
    const t = intent ? intent.type : 'answer';
    switch (t) {
      case 'answer': return (ANSWERS[intent && intent.topic] || ANSWERS.unclear)(after, intent && intent.oppId);
      case 'pause': return 'Paused. Nothing new starts until you say resume.';
      case 'resume': {
        const fresh = Object.values(after.opps).filter((o) => o.receipt === 'unknown_effect' && before.opps[o.id].receipt === 'in_flight');
        return 'Resumed.' + fresh.map((o) => `\n\n${o.employer} may or may not have gone through, so I won't resubmit. Ask me to check it.`).join('');
      }
      case 'draft': case 'redraft': {
        const p = after.pending;
        return `Here's a draft.\n\nWant it in your Gmail drafts? You send it, not me.`; // the draft card (recipient, version, text) goes between
      }
      case 'approve': {
        const a = after.actions[outcome.events[0].actionId]; // built from state.pending, so the id is in the event
        return `Done, it's in your drafts.\nv${a.approved.version} to ${a.approved.recipient}\n\nSimulated here, so no real Gmail draft. You send it, not me.`;
      }
      case 'reconcile': {
        const o = after.opps[intent.oppId];
        return o.receipt === 'confirmed' ? `${who(o)}: ${o.evidence}. Counted once, no retry.` : `${who(o)}: no receipt found. A retry needs your yes.`;
      }
      case 'link': {
        const iv = after.interviews[intent.interviewId];
        return `Done. Linked to ${after.opps[iv.oppId].role}.`;
      }
      case 'manual_done': {
        const retired = Object.values(after.actions).filter((a) => a.status === 'retired' && before.actions[a.id] && before.actions[a.id].status !== 'retired');
        return 'Marked as handled by you.' + (retired.length ? ` ${retired.map((a) => a.id).join(', ')} marked retired in Tsenta's records.` : '');
      }
      case 'route_propose': return `One option, your call: ${after.route.proposed}. Say yes to switch; it can be undone.`;
      case 'route_choose': return `Switched to ${after.route.current}. Say "undo the route" and it goes back.`;
      case 'route_undo': return `Undone. Back to ${after.route.current}.` + (before.route && before.route.proposed ? ` The open proposal (${before.route.proposed}) was dropped.` : '');
      case 'show_status': return Status.statusText(after, intent.section, clock);
      default: return ANSWERS.unclear();
    }
  }

  const api = { say, topics: Object.keys(ANSWERS) };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TsentaVoice = api;
})(this);
