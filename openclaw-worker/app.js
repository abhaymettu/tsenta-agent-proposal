(() => {
  // Thin client for the OpenClaw worker build: the core (server/serve.py) owns the record, the thread and approvals.
  // This page renders stored rows, sends typed messages, and shows the last turn's receipt on S.
  const $ = (id) => document.getElementById(id);
  const thread = $('thread'), input = $('input'), send = $('send'), statePanel = $('state-panel');
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let status = null, receipt = null, busy = Promise.resolve();

  const div = (cls, html) => { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; return d; };
  const append = (el) => { thread.appendChild(el); thread.scrollTop = thread.scrollHeight; return el; };

  // Agent replies arrive as light markdown. Everything is escaped first; the only tags added are <strong> (**bold**, and
  // "#" heading lines), <ul>/<ol> ("- ", "* ", "1. " lines), <p> and <br>. No links, no raw HTML, no attributes.
  function md(text) {
    const inline = (s) => esc(s).replace(/\*\*(?=\S)(.+?)\*\*/g, '<strong>$1</strong>');
    let html = '', list = null, lines = [];
    const flush = () => { if (lines.length) html += `<p>${lines.join('<br>')}</p>`; lines = []; };
    const close = () => { if (list) html += `</${list}>`; list = null; };
    for (const line of String(text).split('\n')) {
      const li = line.match(/^\s*(?:([-*•])|\d+[.)])\s+(.+)$/);
      if (li) {
        const tag = li[1] ? 'ul' : 'ol';
        flush();
        if (list !== tag) { close(); html += `<${tag}>`; list = tag; }
        html += `<li>${inline(li[2])}</li>`;
      } else {
        close();
        const h = line.match(/^\s*#{1,6}\s+(.+)$/);
        if (line.trim()) lines.push(h ? `<strong>${inline(h[1])}</strong>` : inline(line));
      }
    }
    flush(); close();
    return html;
  }

  // A blank line in a message starts a new bubble.
  function addBubble(who, text) {
    for (const part of String(text).split('\n\n')) {
      const last = thread.lastElementChild;
      const same = last && last.classList.contains('msg') && last.classList.contains(who) && !last.classList.contains('typing');
      append(div(`msg ${who}${same ? '' : ' gap'}`, `<div class="bubble">${who === 'them' ? md(part) : esc(part)}</div>`));
    }
  }

  function render(j) {
    status = j;
    thread.innerHTML = '';
    thread.classList.add('instant'); // a stored thread draws at once
    append(div('sys', esc(`Texting as ${j.persona.name} (fictional) · worker ${j.worker.state}`)));
    for (const m of j.messages) m.who === 'sys' ? append(div('sys', esc(m.text))) : addBubble(m.who, m.text);
    $('mode-line').textContent = `Worker: ${j.worker.state}${j.worker.reason ? ' (' + j.worker.reason + ')' : ''} · profile ${j.profile_mode} · core model calls ${j.direct_model_calls}`;
    requestAnimationFrame(() => thread.classList.remove('instant'));
    renderReceipt();
  }

  function renderReceipt() {
    const r = receipt;
    const row = (k, v) => `<div class="row"><div class="k">${k}</div><span class="meta">${esc(v)}</span></div>`;
    const sec = (t, items) => `<div class="sec"><h4>${t}</h4>${items.length ? items.join('') : '<div class="empty">none</div>'}</div>`;
    $('state').innerHTML = !r ? '<div class="empty">No turn yet.</div>' : [
      sec(`Turn ${r.turn} · ${r.persona}`, [row('Worker', r.worker.run_id || r.worker.state), row('Your message', r.user.minted ? 'minted a single-use approval' : (r.user.ask || r.user.note || 'no approval')),
        row('Core model calls', String(r.direct_model_calls))]),
      sec('Tool calls (agent proposed, core decided)', r.tools.map((t) => row(esc(t.tool), t.decision))),
      sec('Sandbox log', r.sandbox_log.map((e) => row(`${esc(e.op)} ${esc(e.key)}`, e.result.receipt || e.result.held || (e.result.counted_once ? 'counted once' : 'ok')))),
    ].join('');
  }

  const typing = () => append(div('msg them typing gap', '<div class="bubble"><i></i><i></i><i></i></div>'));

  async function call(path, body) {
    const res = await fetch(path, { method: path === '/api/thread' ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: path === '/api/thread' ? undefined : JSON.stringify(body || {}) });
    if (!res.ok) throw new Error('backend ' + res.status);
    return res.json();
  }

  const queue = (fn) => (busy = busy.then(fn).catch(() => append(div('sys', 'The demo core is unavailable, so nothing changed.')))) ;

  function sendText(text) {
    return queue(async () => {
      addBubble('me', text); setComposer('');
      const t = typing();
      const j = await call('/api/message', { text }).finally(() => t.remove());
      receipt = j.receipt; render(j);
    });
  }
  const reset = () => queue(async () => { receipt = null; render(await call('/api/reset')); });
  const nextPersona = () => queue(async () => {
    const ids = ['P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07', 'P08', 'P09', 'P10'];
    render(await call('/api/persona', { id: ids[(ids.indexOf(status.persona.id) + 1) % ids.length] }));
  });

  function setComposer(text) { input.value = text || ''; send.classList.toggle('ready', !!text); }
  const toggleState = (open) => { const on = statePanel.classList.toggle('open', open); document.body.classList.toggle('debug', on); };

  $('reset').addEventListener('click', reset);
  $('m-reset').addEventListener('click', reset);
  $('r-state').addEventListener('click', () => toggleState());
  $('m-state').addEventListener('click', () => toggleState(true));
  $('state-close').addEventListener('click', () => toggleState(false));
  send.addEventListener('click', () => { const v = input.value.trim(); if (v) sendText(v); });
  input.addEventListener('input', () => send.classList.toggle('ready', !!input.value.trim()));
  document.addEventListener('keydown', (e) => {
    if (document.activeElement === input) {
      if (e.key === 'Enter') { e.preventDefault(); send.click(); }
      if (e.key === 'Escape') input.blur();
      return;
    }
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'r' || e.key === 'R') reset();
    else if (e.key === 's' || e.key === 'S') toggleState();
    else if (e.key === ']') nextPersona();
  });

  if (new URLSearchParams(location.search).get('debug') === '1') toggleState(true);
  queue(async () => { const j = await call('/api/thread'); receipt = j.receipt || null; render(j); });
  window.TsentaDemo = { status: () => status, send: sendText, reset, nextPersona, md }; // hook for the capture tool
})();
