(() => {
  const Core = window.TsentaCore;
  const SCENES = window.TSENTA_SCENES;
  const $ = (id) => document.getElementById(id);
  const thread = $('thread'), input = $('input'), send = $('send'), statePanel = $('state-panel');
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // Flatten scenes into one thread: the conversation runs across a week.
  const STEPS = SCENES.flatMap((sc, i) => sc.steps.map((st) => Object.assign({ scene: i }, st)));

  let state, scene, pos, pendingUser, busy, token = 0, instant = false, live = null, prevRows = {};
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
    invite: (s) => {
      const iv = s.interviews.I1;
      return `<div class="card-label">Interview request</div>` +
        row(`From<small>${esc(iv.from)}</small>`, '') +
        row(`Role`, iv.oppId ? pill('ok', s.opps[iv.oppId].role) : pill('unk', `not linked · ${iv.candidates.length} possible`)) +
        iv.candidates.map((id) => row(`<small>${esc(s.opps[id].role)}</small>`, pill(...RECEIPT[s.opps[id].receipt]))).join('');
    },
    draft: (s, id) => {
      const a = s.actions[id], v = a.versions[a.versions.length - 1];
      return `<div class="card-label">Draft ${esc(a.id)} · v${v.v}</div><div class="quote">${esc(v.body)}</div>
        <div class="meta">To ${esc(a.recipient)} · Gmail draft · you send it</div>`;
    },
    approved: (s, id) => {
      const a = s.actions[id];
      return `<div class="card-label">Your yes bound to</div>` +
        row('Action', pill('off', `${a.id} · reply to Halyard`)) +
        row('Version', pill('off', `v${a.approved.version} (the one you saw)`)) +
        row('Recipient', `<span class="meta">${esc(a.approved.recipient)}</span>`) +
        row('Status', pill('ok', 'in your Gmail drafts'));
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
        let p = o.receipt === 'confirmed' ? pill('off', 'quiet · mail healthy') : pill('unk', 'unknown · no receipt');
        if (iv && iv.status === 'cancelled') p = pill('ask', 'awaiting new time');
        return row(`${esc(o.employer)}<small>${esc(o.role)} · applied ${esc(o.applied)}</small>`, p);
      });
      rows.push(row(`School Outlook<small>since ${esc(out.since)}</small>`, pill('unk', "disconnected · can't see")));
      return `<div class="card-label">Where things stand</div>${rows.join('')}
        <div class="meta" style="margin-top:6px">No rejection observed. Quiet is not a no.</div>`;
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
  function addBubble(who, text, tag) {
    const last = thread.lastElementChild;
    const same = last && last.classList.contains('msg') && last.classList.contains(who) && !last.classList.contains('typing');
    if (same) last.querySelector('.bubble').classList.remove('tail');
    const m = div(`msg ${who}${same ? '' : ' gap'}`, `<div class="bubble tail">${esc(text)}</div>`);
    if (who === 'me') {
      thread.querySelectorAll('.delivered').forEach((d) => d.remove());
      m.appendChild(div('delivered', 'Delivered'));
    }
    if (tag) m.appendChild(div('live-tag', esc(tag)));
    return append(m);
  }
  function addCard(name) {
    const [kind, id] = name.split(':');
    const last = thread.lastElementChild;
    if (last && last.classList.contains('them')) last.querySelector('.bubble').classList.remove('tail');
    append(div('card', CARDS[kind](state, id)));
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
    token++; hurry();
    state = Core.initial(); scene = 0; pos = 0; pendingUser = null; busy = false; prevRows = {};
    thread.innerHTML = ''; setComposer('');
    instant = true; thread.classList.add('instant');
    for (scene = 0; scene <= target; scene++) {
      if (scene === target && !all) break;
      while (pos < STEPS.length && STEPS[pos].scene === scene) {
        const st = STEPS[pos];
        if (st.t === 'user') { addBubble('me', st.text); applyAll(st.ev); } else await show(st, token);
        pos++;
      }
    }
    scene = target;
    renderState();
    await new Promise(requestAnimationFrame);
    instant = false; thread.classList.remove('instant');
    renderRail();
    if (!all) runAuto();
  }

  /* ---------- live mode (server/serve.py, Claude behind docs/CONTRACT.md) ---------- */
  async function sendLive(text) {
    while (busy) { hurry(); await new Promise((r) => setTimeout(r, 50)); } // finish scripted auto-play first, so replies never interleave
    addBubble('me', text);
    setComposer('');
    const t = append(div('msg them typing gap', '<div class="bubble"><i></i><i></i><i></i></div>'));
    let reply, tag;
    try {
      const res = await fetch('/api/agent', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userText: text, scene: scene + 1, state, pending: state.pending }),
      });
      const j = await res.json();
      if (res.ok) {
        reply = j.reply; tag = j.mode === 'live' ? `Claude · live · $${(j.spentUsd || 0).toFixed(3)} spent` : `scripted · ${j.mode}`;
        if (j.intent) {
          const e = j.intent.type === 'approve' ? { type: 'yes', actionId: j.intent.actionId, version: j.intent.version } : j.intent;
          if (Core.types.includes(e.type)) applyAll([e]);
        }
      } else { reply = 'Live mode is off right now, so this demo stays scripted.'; tag = `mock · ${j.mode || res.status}`; }
    } catch (err) { reply = 'Live mode is unavailable, so this demo stays scripted.'; tag = 'mock · offline'; }
    t.remove();
    addBubble('them', reply, tag);
    setComposer(pendingUser ? pendingUser.text : '');
  }

  async function detectLive() {
    try {
      const j = await (await fetch('/api/status')).json();
      live = j.mode === 'live' ? j : null;
      $('mode-line').textContent = live
        ? `Mode: scripted scenes + live Claude for typed messages (cap $${j.capUsd}, spent $${(j.spentUsd || 0).toFixed(2)})`
        : 'Mode: scripted';
      $('mode-line').title = live ? '' : (j.reason || 'live off');
    } catch { $('mode-line').textContent = 'Mode: scripted (offline)'; }
    input.placeholder = live ? 'iMessage · type to ask live' : 'iMessage';
  }

  /* ---------- wiring ---------- */
  const toggleState = (open) => statePanel.classList.toggle('open', open);
  $('next').addEventListener('click', next);
  $('reset').addEventListener('click', () => goTo(0));
  $('m-reset').addEventListener('click', () => goTo(0));
  $('r-state').addEventListener('click', () => toggleState());
  $('m-state').addEventListener('click', () => toggleState(true));
  $('state-close').addEventListener('click', () => toggleState(false));
  $('scenes').addEventListener('click', (e) => { const b = e.target.closest('.scene-btn'); if (b) goTo(+b.dataset.i); });
  send.addEventListener('click', () => {
    const v = input.value.trim();
    if (v && (!pendingUser || v !== pendingUser.text)) return sendLive(v); // typed text: live Claude, or a canned reply in mock
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
    else if (e.key === 'r' || e.key === 'R') goTo(0);
    else if (e.key === 'ArrowLeft') goTo(Math.max(0, scene - 1));
    else if (/^[1-9]$/.test(e.key) && +e.key <= SCENES.length) goTo(+e.key - 1);
    else if (e.key === 's' || e.key === 'S') toggleState();
  });

  const q = new URLSearchParams(location.search);
  const startAt = Math.min(SCENES.length, Math.max(1, +q.get('scene') || 1)) - 1;
  goTo(startAt, q.get('step') === 'all').then(() => { if (q.get('state') === 'open') toggleState(true); });
  detectLive();
  window.TsentaDemo = { state: () => state, scene: () => scene }; // read-only hook for tests/e2e.mjs
})();
