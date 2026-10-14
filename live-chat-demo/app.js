(() => {
  const Core = window.TsentaCore;
  const SCENES = window.TSENTA_SCENES;
  const $ = (id) => document.getElementById(id);
  const thread = $('thread'), input = $('input'), send = $('send'), statePanel = $('state-panel');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // Flatten scenes into one thread: the conversation runs across a week.
  const STEPS = SCENES.flatMap((sc, i) => sc.steps.map((st) => Object.assign({ scene: i }, st)));

  let state, scene, pos, pendingUser, busy, token = 0, rebuild = 0, seen = -1, threadLoaded = false, instant = false, live = null, prevRows = {};
  let waiters = [];

  const wait = (ms) => new Promise((r) => {
    if (instant) return r();
    const t = setTimeout(r, reduce ? Math.min(ms, 250) : ms);
    waiters.push(() => { clearTimeout(t); r(); });
  });
  const hurry = () => { waiters.splice(0).forEach((f) => f()); };

  /* ---------- cards: rendered from deterministic state at the moment shown ---------- */
  const pill = (cls, text) => `<span class="pill ${cls}">${esc(text)}</span>`;
  const row = (k, v) => `<div class="row"><div class="k">${k}</div>${v}</div>`;
  const RECEIPT = {
    confirmed: ['ok', 'receipt'], attempted: ['unk', 'attempt only'], queued: ['off', 'queued'],
    in_flight: ['unk', 'in flight'], unknown_effect: ['unk', 'maybe sent · checking'], not_found: ['no', 'no receipt'],
  };
  const SOURCE = { healthy: ['ok', 'connected'], disconnected: ['unk', 'disconnected'], not_connected: ['off', "can't see"] };
  const RULE = { auto: ['ok', 'on its own'], ask: ['ask', 'asks you'], never: ['no', 'never'] };

  const CARDS = {
    goal: (s) => `<div class="card-label">Goal</div><div class="quote">${esc(s.goal.text)}</div>
      <div class="chips">${s.goal.constraints.map((c) => `<span class="chip">${esc(c)}</span>`).join('')}</div>`,
    coverage: (s) => `<div class="card-label">What I can see</div>` +
      Object.values(s.sources).map((x) => row(esc(x.label), pill(...SOURCE[x.status]))).join(''),
    permissions: (s) => `<div class="card-label">Permissions · epoch ${s.epoch}</div>` +
      s.permissions.map((p) => row(esc(p.what), pill(...RULE[p.rule]))).join(''),
    receipts: (s) => `<div class="card-label">Applications</div>` +
      Object.values(s.opps).map((o) => row(`${esc(o.employer)}<small>${esc(o.role)} · ${esc(o.applied)}</small>`, pill(...RECEIPT[o.receipt]))).join(''),
    invite: (s, id = 'I1') => {
      const iv = s.interviews[id];
      return `<div class="card-label">Interview request</div>` +
        row(`From<small>${esc(iv.from)}</small>`, '') +
        row(`Role`, iv.oppId ? pill('ok', s.opps[iv.oppId].role) : pill('unk', `not linked · ${iv.candidates.length} possible`)) +
        iv.candidates.map((id) => row(`<small>${esc(s.opps[id].role)}</small>`, pill(...RECEIPT[s.opps[id].receipt]))).join('');
    },
    draft: (s, id) => { // shown like a quoted message: who it goes to, the text, and who wrote it
      const a = s.actions[id], v = a.versions[a.versions.length - 1];
      const iv = a.taskId && s.tasks[a.taskId] && s.tasks[a.taskId].interviewId ? s.interviews[s.tasks[a.taskId].interviewId] : null;
      return `<div class="draft-to">To ${esc(a.recipient)} · v${v.v}</div><div class="draft-body">${esc(v.body)}</div>` +
        (v.by === 'claude' ? `<div class="draft-by">Written by Claude · check it first${iv && !iv.oppId ? ' · role not linked yet' : ''}</div>` : '');
    },
    approved: (s, id) => {
      const a = s.actions[id];
      return `<div class="card-label">Your yes bound to</div>` +
        row('Action', pill('off', `${a.id} · reply to ${a.taskId && s.tasks[a.taskId] && s.tasks[a.taskId].interviewId ? s.interviews[s.tasks[a.taskId].interviewId].employer : 'recruiter'}`)) +
        row('Version', pill('off', `v${a.approved.version} (the one you saw)`)) +
        row('Recipient', `<span class="meta">${esc(a.approved.recipient)}</span>`) +
        row('Status', pill('ok', 'in Gmail drafts (simulated)'));
    },
    interview: (s, id) => {
      const iv = s.interviews[id], r = Object.values(s.reminders).find((x) => x.interviewId === id && x.status === 'active');
      return `<div class="card-label">Interview · rev ${iv.rev}</div>` +
        row(`${esc(iv.employer)}<small>${iv.oppId ? esc(s.opps[iv.oppId].role) : 'role unknown'}</small>`, pill('ok', iv.status)) +
        row('Time', `<span class="meta">${esc(iv.time || '—')}</span>`) +
        row('Prep + reminder', r ? pill('ok', 'set for this time') : pill('off', 'none'));
    },
    silence: (s) => {
      const out = s.sources.outlook;
      const rows = Object.values(s.opps).map((o) => {
        const iv = Object.values(s.interviews).find((x) => x.oppId === o.id);
        const r = Core.replyStatus(s, o.id).status; // the same status live replies and the status text use
        let p = o.receipt !== 'confirmed' ? pill('unk', 'unknown · no receipt') : r === 'replied' ? pill('ok', 'replied') : r === 'maybe_replied' ? pill('unk', 'maybe replied') : r === 'waiting' ? pill('off', 'quiet · mail healthy') : pill('unk', 'reply unknown · mail down');
        if (iv && iv.status === 'cancelled') p = pill('ask', 'cancelled · no new time');
        return row(`${esc(o.employer)}<small>${esc(o.role)} · applied ${esc(o.applied)}</small>`, p);
      });
      rows.push(row(`School Outlook<small>since ${esc(out.since)}</small>`, pill('unk', "disconnected · can't see")));
      return `<div class="card-label">Where things stand</div>${rows.join('')}
        <div class="meta" style="margin-top:6px">Rejections aren't tracked here. No reply on record is not a no.</div>`;
    },
    route: (s) => `<div class="card-label">Proposed change · reversible</div>` +
      row(`Now<small>${esc(s.route.current)}</small>`, '') +
      row(`Proposed<small>${esc(s.route.proposed)}</small>`, pill('ask', 'your call')) +
      `<div class="meta" style="margin-top:6px">Outcome data in this demo is synthetic. Tsenta's founder described seeing which companies send interviews; that capability is assumed here, not shown.</div>`,
  };

  /* ---------- thread ---------- */
  function scrollEnd() { thread.scrollTop = thread.scrollHeight; }
  function append(el) { thread.appendChild(el); scrollEnd(); return el; }
  function div(cls, html) { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; return d; }

  function addStamp(text) {
    const [day, ...rest] = text.split(' ');
    append(div('stamp', `<b>${esc(day)}</b> ${esc(rest.join(' '))}`));
  }
  // A blank line in a message starts a new bubble: the agent texts in short turns, as people do.
  function addBubble(who, text, tag) {
    let m;
    for (const part of String(text).split('\n\n')) {
      const last = thread.lastElementChild;
      const same = last && last.classList.contains('msg') && last.classList.contains(who) && !last.classList.contains('typing');
      m = append(div(`msg ${who}${same ? '' : ' gap'}`, `<div class="bubble">${esc(part)}</div>`));
    }
    if (tag) m.appendChild(div('live-tag', esc(tag))); // debug view only
    return m;
  }
  function addCard(name, s = state) { // s: the state the card shows (a stored live card carries its own)
    const [kind, id] = name.split(':');
    append(div(`card card-${kind}`, CARDS[kind](s, id))); // the presenter view shows only the draft; the rest is debug
  }
  async function typing(ms) {
    const t = append(div('msg them typing gap', '<div class="bubble"><i></i><i></i><i></i></div>'));
    await wait(ms);
    t.remove();
  }

  /* ---------- state panel ---------- */
  // Silence on a sent application, from Core.replyStatus: waiting when mail is healthy, unknown when a source is down.
  const replyNote = (s, o) => {
    const r = Core.replyStatus(s, o.id);
    return r.status === 'replied' ? ' · employer replied' : r.status === 'waiting' ? ' · no reply yet, waiting' : r.status === 'unknown' ? ` · reply unknown, ${esc(r.why.map((w) => w.replace(/ since .*/, '')).join('; '))}` : '';
  };

  function renderState() {
    const s = state, rows = {};
    const r = (key, k, v) => { rows[key] = k + v; return `<div class="row" data-key="${esc(key)}"><div class="k">${k}</div>${v}</div>`; };
    const sec = (title, items) => `<div class="sec"><h4>${title}</h4>${items.length ? items.join('') : '<div class="empty">—</div>'}</div>`;
    const html = [
      sec('Goal', s.goal ? [r('goal', esc(s.goal.text), '')] : []),
      sec(`Permissions · epoch ${s.epoch}`, s.permissions.map((p, i) => r('perm' + i, esc(p.what), pill(...RULE[p.rule])))),
      sec('Sources', Object.values(s.sources).map((x) => r('src' + x.id, esc(x.label), pill(...SOURCE[x.status])))),
      sec('Opportunities', Object.values(s.opps).map((o) => r('opp' + o.id, `${esc(o.employer)}<small>${esc(o.role)}${replyNote(s, o)}</small>`, pill(...RECEIPT[o.receipt])))),
      sec('Interviews', Object.values(s.interviews).map((iv) => r('iv' + iv.id,
        `${esc(iv.employer)} · rev ${iv.rev}<small>${iv.oppId ? esc(s.opps[iv.oppId].role) : 'not linked'}${iv.time ? ' · ' + esc(iv.time) : ''}</small>`,
        pill(iv.status === 'cancelled' ? 'off' : iv.status === 'confirmed' ? 'ok' : 'unk', iv.status.replace('_', ' '))))),
      sec('Tasks', Object.values(s.tasks).map((t) => r('task' + t.id, `${esc(t.title)}${t.by ? '<small>done by candidate</small>' : ''}`,
        pill(t.status === 'completed' ? 'ok' : t.status === 'awaiting_user' ? 'ask' : 'off', t.status.replace('_', ' '))))),
      sec('Actions', Object.values(s.actions).map((a) => r('act' + a.id, `${esc(a.id)} · v${a.versions.length}<small>${esc(a.recipient)}</small>`,
        pill(a.status === 'retired' ? 'off' : a.status === 'placed' || a.status === 'approved' ? 'ok' : 'ask', a.status)))),
      sec('Waiting for a yes', s.pending ? [r('pending', `${esc(s.pending.actionId)} · v${s.pending.version}<small>${esc(s.pending.recipient)}</small>`, pill('ask', 'open question'))] : []),
      sec('Reminders', Object.values(s.reminders).map((x) => r('rem' + x.id, esc(x.label), pill(x.status === 'active' ? 'ok' : 'off', x.status)))),
      sec('Route', s.route ? [r('route', `${esc(s.route.current)}${s.route.proposed ? `<small>proposed: ${esc(s.route.proposed)}</small>` : s.route.previous ? '<small>undo available</small>' : ''}`, '')] : []),
      `<div class="sec"><h4>Event log</h4><div class="log">${s.log.slice(-12).map((l) =>
        `<div class="${l.flag || ''}" data-key="log${l.seq}">${String(l.seq).padStart(2, '0')} ${esc(l.text)}</div>`).join('')}</div></div>`,
    ].join('');
    $('state').innerHTML = html;
    if (!instant) {
      for (const el of $('state').querySelectorAll('[data-key]')) {
        const k = el.dataset.key;
        const changed = k.startsWith('log') ? !(k in prevRows) : prevRows[k] !== rows[k];
        if (changed) el.classList.add('flash');
      }
    }
    prevRows = Object.assign({}, rows);
    for (const l of s.log) prevRows['log' + l.seq] = 1;
  }

  function applyAll(evs) { for (const e of evs || []) state = Core.apply(state, e); renderState(); }

  /* ---------- playback ---------- */
  function renderRail() {
    $('scenes').innerHTML = SCENES.map((sc, i) => `<li><button class="scene-btn${i < scene ? ' done' : ''}" data-i="${i}" ${i === scene ? 'aria-current="true"' : ''}>
      <span class="scene-num">${i + 1}</span><span class="scene-title">${esc(sc.title)}</span><span class="scene-principle">${esc(sc.principle)}</span></button></li>`).join('');
    $('mobile-scene').textContent = `${scene + 1}/${SCENES.length} · ${SCENES[scene].title}`;
    $('mobile-scene').title = SCENES[scene].principle;
    const atEnd = !busy && !pendingUser && (pos >= STEPS.length || STEPS[pos].scene !== scene);
    $('next').firstChild.textContent = atEnd ? (scene < SCENES.length - 1 ? 'Next scene ' : 'Finished ') : 'Next ';
  }

  async function show(st, my) {
    if (st.t === 'time') addStamp(st.text);
    else if (st.t === 'sys') { await wait(450); if (my !== token) return; applyAll(st.ev); append(div('sys', esc(st.text))); }
    else if (st.t === 'aside') { await wait(500); if (my !== token) return; append(div('aside', esc(st.text))); }
    else if (st.t === 'agent') {
      await typing(Math.min(1300, Math.max(550, st.text.length * 11)));
      if (my !== token) return;
      applyAll(st.ev);
      addBubble('them', st.text);
      if (st.card) { await wait(160); if (my !== token) return; addCard(st.card); }
    }
  }

  function setComposer(text) {
    input.value = text || '';
    send.classList.toggle('ready', !!text);
  }

  async function runAuto() {
    const my = ++token;
    busy = true; renderRail();
    while (pos < STEPS.length && STEPS[pos].scene === scene) {
      const st = STEPS[pos];
      if (st.t === 'user') { pendingUser = st; setComposer(st.text); break; }
      await show(st, my);
      if (my !== token) return;
      pos++;
    }
    busy = false; renderRail();
    maybeLoadThread();
  }

  async function sendUser() {
    const st = pendingUser; pendingUser = null;
    setComposer('');
    addBubble('me', st.text);
    applyAll(st.ev);
    pos++;
    await wait(250);
    await runAuto();
  }

  function next() {
    if (busy) return hurry();
    if (pendingUser) return sendUser();
    if (pos < STEPS.length && STEPS[pos].scene === scene) return runAuto();
    if (scene < SCENES.length - 1) { scene++; return runAuto(); }
  }

  // Jump: rebuild everything before `target` instantly, then play the target live (or instantly when all=true).
  async function goTo(target, all) {
    token++; rebuild++; hurry();
    state = Core.initial(); scene = 0; pos = 0; pendingUser = null; busy = false; prevRows = {}; seen = -1; threadLoaded = false;
    thread.innerHTML = ''; setComposer('');
    append(div('disclosure', 'Demo · synthetic people and jobs · nothing is sent'));
    instant = true; thread.classList.add('instant');
    const quiet = target === SCENES.length - 1 && !document.body.classList.contains('debug'); // presenter: scene 6 starts clean
    for (scene = 0; scene <= target; scene++) {
      if (scene === target && !all) break;
      while (pos < STEPS.length && STEPS[pos].scene === scene) {
        const st = STEPS[pos];
        if (quiet && scene < target) applyAll(st.ev);
        else if (st.t === 'user') { addBubble('me', st.text); applyAll(st.ev); } else await show(st, token);
        pos++;
      }
    }
    scene = target;
    renderState();
    await new Promise(requestAnimationFrame);
    instant = false; thread.classList.remove('instant');
    renderRail();
    if (!all) runAuto(); else maybeLoadThread();
  }

  /* ---------- live mode (variant): the scene-6 conversation lives in the demo backend (server/serve.py, SQLite) ---------- */
  // The backend runs the rules (core.js, intents.js, voice.js in server/worker.js) and keeps state and the thread across
  // reloads and restarts. The browser renders what the backend stored. Scenes 1 to 5 stay a scripted walkthrough.
  // seen: how many backend agent messages are on screen, sent with each message, so a yes typed before a newer agent
  // message never answers the older question. -1 after a message the backend did not store: nothing can be answered.
  let liveQueue = Promise.resolve(), loading = false;
  function addRow(m) {
    if (m.who === 'sys') return append(div('sys', esc(m.text)));
    if (!m.card || !m.text.includes('\n\n')) { addBubble(m.who, m.text, m.tag); if (m.card) addCard(m.card, m.cardState); return; }
    const [first, ...rest] = m.text.split('\n\n'); // "Here's a draft", the draft itself, then the question about it
    addBubble(m.who, first);
    addCard(m.card, m.cardState);
    addBubble(m.who, rest.join('\n\n'), m.tag);
  }

  async function loadThread() {
    const my = rebuild;
    loading = true;
    try {
      const j = await (await fetch('/api/thread')).json();
      if (my !== rebuild) return;
      state = j.state; renderState();
      append(div('sys', esc(`Demo backend on this Mac: ${j.events} events in SQLite, seeded demo data (${j.seededAt}). The thread below survives reloads and restarts.`)));
      j.messages.forEach(addRow);
      seen = j.seen; threadLoaded = true;
    } catch { if (my === rebuild) append(div('sys', 'Demo backend unavailable: typing stays off.')); }
    finally { loading = false; }
  }
  const maybeLoadThread = () => { if (live && !threadLoaded && !loading && !busy && scene === SCENES.length - 1 && pos >= STEPS.length) loadThread(); };

  // One message at a time; `seen` and the idempotency key are fixed when Maya presses send.
  // gen: a scene jump or reset after she pressed send makes the message stale before it is sent.
  const sendLive = (text) => { const mark = seen, key = crypto.randomUUID(), gen = rebuild; return (liveQueue = liveQueue.then(() => sendLiveOne(text, mark, key, gen)).catch(() => {})); };

  async function sendLiveOne(text, mark, key, gen) {
    while (busy) { hurry(); await new Promise((r) => setTimeout(r, 50)); } // finish scripted auto-play first, so replies never interleave
    while (loading) await new Promise((r) => setTimeout(r, 50)); // the stored thread is on its way: her bubble goes after it
    const my = rebuild; // a scene jump or reset from here on makes the response stale
    if (gen !== my) return;
    addBubble('me', text);
    setComposer('');
    if (!threadLoaded) {
      seen = -1;
      addBubble('them', live ? 'Typing goes to the demo backend in scene 6 ("Your turn"). Press 6 to jump there.' : 'The demo backend is not running, so typed messages go nowhere.', 'not stored');
      return;
    }
    const t = append(div('msg them typing gap', '<div class="bubble"><i></i><i></i><i></i></div>'));
    try {
      const res = await fetch('/api/message', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, key, seen: mark }), signal: AbortSignal.timeout(25000),
      });
      const j = await res.json().catch(() => ({}));
      if (my !== rebuild) return;
      if (res.status === 409 || res.status === 503) { // nothing stored: the thread changed elsewhere, or another message is being answered
        t.remove(); seen = -1;
        addBubble('them', res.status === 409 ? 'The demo changed in another window, so nothing was shown or changed. Reload, then send again.' : "I'm still answering an earlier message, so this one wasn't sent. Send it again in a moment.", 'not stored');
        return setComposer(text);
      }
      if (!res.ok || !Array.isArray(j.messages)) throw new Error('backend ' + res.status);
      t.remove();
      j.messages.filter((m) => m.who !== 'me').forEach(addRow);
      state = j.state; renderState(); seen = j.seen;
    } catch (err) {
      if (my !== rebuild) return;
      t.remove();
      seen = -1; // this note is now the latest message, and the backend never stored it
      addBubble('them', err && err.name === 'TimeoutError'
        ? 'That took too long. The backend may still have handled it; reload to see the stored thread.'
        : 'The demo backend is unavailable right now, so nothing was shown or changed. Try again.', 'not stored');
    }
    setComposer(pendingUser ? pendingUser.text : '');
  }

  async function resetAll() {
    rebuild++; threadLoaded = false; seen = -1; // anything still queued or in flight is stale from here: nothing more is sent or shown
    await liveQueue;
    let ok = !live;
    if (live) { try { ok = (await fetch('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).ok; } catch { ok = false; } }
    await goTo(scene === SCENES.length - 1 ? scene : 0, scene === SCENES.length - 1); // reset keeps the presenter on scene 6
    if (!ok) $('mode-line').textContent += ' · reset failed: the stored thread is unchanged';
  }

  async function detectLive() {
    try {
      const j = await (await fetch('/api/status')).json();
      live = j.backend ? j : null;
      $('mode-line').textContent = !live ? 'Mode: scripted'
        : j.mode === 'live' ? `Mode: demo backend · ${String(j.model).replace('claude-', '')} proposes, code decides · spent $${(j.spentUsd || 0).toFixed(3)} (estimate)`
        : `Mode: demo backend · Claude not connected (${j.reason || j.mode}); code answers what it can`;
    } catch { $('mode-line').textContent = 'Mode: scripted (offline)'; }
    maybeLoadThread();
  }

  /* ---------- wiring ---------- */
  // Debug view (S, or ?debug=1): the state panel, scene list, events and per-message tags. The presenter view hides them.
  const toggleState = (open) => { const on = statePanel.classList.toggle('open', open); document.body.classList.toggle('debug', on); };
  $('next').addEventListener('click', next);
  $('reset').addEventListener('click', resetAll); // also clears the demo backend's thread
  $('m-reset').addEventListener('click', resetAll);
  $('r-state').addEventListener('click', () => toggleState());
  $('m-state').addEventListener('click', () => toggleState(true));
  $('state-close').addEventListener('click', () => toggleState(false));
  $('scenes').addEventListener('click', (e) => { const b = e.target.closest('.scene-btn'); if (b) goTo(+b.dataset.i); });
  send.addEventListener('click', () => {
    const v = input.value.trim();
    if (v && (!pendingUser || v !== pendingUser.text)) return sendLive(v); // typed text: the backend (scene 6)
    next();
  });
  input.addEventListener('input', () => send.classList.toggle('ready', !!input.value.trim()));
  thread.addEventListener('click', () => { if (matchMedia('(max-width: 760px)').matches) next(); });
  document.addEventListener('keydown', (e) => {
    if (document.activeElement === input) {
      if (e.key === 'Enter') { e.preventDefault(); send.click(); }
      if (e.key === 'Escape') input.blur();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === ' ' || e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); next(); }
    else if (e.key === 'r' || e.key === 'R') resetAll();
    else if (e.key === 'ArrowLeft') goTo(Math.max(0, scene - 1));
    else if (/^[1-9]$/.test(e.key) && +e.key <= SCENES.length) goTo(+e.key - 1);
    else if (e.key === 's' || e.key === 'S') toggleState();
  });

  const q = new URLSearchParams(location.search);
  const startAt = Math.min(SCENES.length, Math.max(1, +q.get('scene') || 1)) - 1;
  if (q.get('debug') === '1' || q.get('state') === 'open') toggleState(true);
  goTo(startAt, q.get('step') === 'all');
  detectLive();
  window.TsentaDemo = { state: () => state, scene: () => scene }; // hook for tests and snapshots
})();
