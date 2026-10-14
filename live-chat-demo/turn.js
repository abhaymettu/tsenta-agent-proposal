// One typed message through the rules, as the backend runs it. Pure: no I/O, no model call.
// turn(state, question, text) -> { needModel: true } when only a model can read the message; then call again with the
// model's proposed intent. Otherwise -> { state, events, reply, question, card, kind, proposed }:
//   state: after accepted events; question: the only question Maya's next message can answer locally;
//   kind: 'local' (no model call) or 'model'; proposed: the model's intent type when code declined it.
(function (root) {
  const req = (n, g) => root[g] || (typeof require !== 'undefined' ? require(n) : null);
  const Core = req('./core.js', 'TsentaCore'), Intents = req('./intents.js', 'TsentaIntents');
  const Voice = req('./voice.js', 'TsentaVoice'), FX = req('./fixtures.js', 'TSENTA_FIXTURES');

  function turn(state, question, text, intent, clock) {
    let outcome = Intents.local(state, question, text, FX), kind = 'local';
    if (!outcome) {
      if (intent === undefined) return { needModel: true };
      outcome = Intents.toEvents(state, intent, FX, text);
      kind = 'model';
    }
    const events = outcome.ok ? outcome.events : [];
    const after = events.reduce(Core.apply, state);
    let reply;
    try { reply = Voice.say(state, after, outcome.intent || intent, outcome, clock); } catch (err) { // never claim nothing happened after events applied
      reply = outcome.ok ? `Done: ${events.map((e) => e.type).join(', ') || 'nothing changed'}.` : "That didn't go through.";
    }
    const declined = kind === 'model' && !outcome.ok && !outcome.confirm && !outcome.clarify && intent;
    return {
      state: after, events, reply,
      question: outcome.confirm || outcome.followUp || outcome.which || null,
      card: outcome.ok && outcome.card && !outcome.card.startsWith('status:') ? outcome.card : null, // status is text now
      kind, proposed: declined ? intent.type : null,
      waiting: outcome.confirm ? 'yes' : outcome.clarify ? 'which' : null,
    };
  }

  const api = { turn };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TsentaTurn = api;
})(this);
