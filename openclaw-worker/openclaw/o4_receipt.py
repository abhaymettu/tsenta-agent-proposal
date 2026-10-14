"""O4 core-restart durability receipt (569 DECISION and FINDINGS section 4; operator SYNTH0111, GOOFFLINE0114).

O4 is a core-only restart, judged on what the processes serve and what OpenClaw's session row says, never on file bytes:
  1. the restart happened: a new core pid and a "token pushed: yes" boot line; worker and edge Id/StartedAt and the
     gateway pid unchanged;
  2. the restarted core serves the same thread, generation, session key and record state, and receipts.jsonl keeps
     its prefix;
  3. OpenClaw's row for the session key keeps its sessionId and sessionStartedAt (matched case-insensitively: the store
     lowercases the key, 569 F8);
  4. the first turn after the restart runs on that session: a new run id and the same sessionId (the primary
     evidence). totalTokens no smaller than before is weak consistency evidence only, not proof the context was loaded
     (totals can reset and reinflate from other context); a smaller value may be compaction, so it is UNKNOWN, never a
     FAIL on its own (569 F3). Whether the first reply actually uses pre-restart facts is a manual check (MANUAL line).
The restart may happen only while the core is idle (active_turn false, not missing) and its last receipt is complete:
a real run id and no worker state (569 F7). Session fields must be non-empty: an empty sessionId or sessionStartedAt
is UNKNOWN, never "unchanged" (the exact sessions --json shape at the pin awaits 551's trace). Full O4 needs all three
captures; comparing only before and after gives PARTIAL, never PASS (operator O4SOURCE0142). A worker or Gateway
restart wipes OpenClaw's tmpfs state: it is a total reset, never O4, and out of scope here (569 F5). An unreadable
sessions listing is UNKNOWN, never PASS.

Every capture is read-only: two GETs, a read of run/receipts.jsonl, docker inspect and top, lsof, and
`openclaw sessions --json` inside the worker. Its first live use needs the operator's GO, and 551 reviews the
sessions command first (569 section 5).

  python3 openclaw/o4_receipt.py capture OUT.json --core-log PATH [--persona P01]   (before, after the restart, after a turn)
  python3 openclaw/o4_receipt.py compare PRE.json POST.json [TURN.json]
Exit 0 PASS (the MANUAL read still pending), 1 FAIL, 2 UNKNOWN, 3 PARTIAL, 64 usage error.
"""
import argparse, hashlib, json, os, subprocess, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_prompts as rp

MANUAL = 'check by reading: the first post-restart reply uses facts from before the restart (the totals do not prove it)'
# 551 v114 (O4RESIDUAL0157, traced, not run): this path runs no config doctor, loads no plugins, makes no network call
# and opens the agent DB readOnly. The env guards stop its three side effects: a compile cache in /tmp, a respawned
# second node, and the file logger appending to the gateway's /tmp/openclaw/openclaw.log. `timeout 30` runs inside the
# container, because the subprocess timeout kills only the docker client. Est. 150-300 MB RSS in the key container
# (not measured): live use is the operator's ruling, with its own GO. -u node as the other execs here (552): a
# root CLI touching the WAL database could leave root-owned files.
SESSIONS = [*rp.D, 'exec', '-u', 'node', '-e', 'OPENCLAW_NO_RESPAWN=1', '-e', 'NODE_DISABLE_COMPILE_CACHE=1', '-e', 'OPENCLAW_LOG_LEVEL=silent',
            'oc551-worker', 'timeout', '30', 'openclaw', 'sessions', '--agent', 'main', '--json']


def sh(argv):
    r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else None


def session_row(text, key):
    """OpenClaw's row for the core's session key: None when unreadable or key-shaped, or when absent from a listing
    that is not explicitly complete (hasMore true, missing or not a boolean, or a bare list); {} only when absent from
    a listing with hasMore exactly false (operator SOURCE0158). Shape at the pin (551 v112): {path, count, totalCount,
    limitApplied, hasMore, activeMinutes, sessions: [{key, sessionId?, sessionStartedAt?, totalTokens|null,
    totalTokensFresh, updatedAt}]}; newest first, default limit 100; no compactionCount field."""
    if text is None or rp.KEY_SHAPED in text:
        return None
    try:
        j = json.loads(text)
    except ValueError:
        return None
    rows = j.get('sessions', j.get('rows')) if isinstance(j, dict) else j
    if not isinstance(rows, list):
        return None
    want = 'agent:main:' + key.lower()
    row = next((r for r in rows if isinstance(r, dict) and str(r.get('key', '')).lower() == want), None)
    if row is None:
        return {} if isinstance(j, dict) and j.get('hasMore') is False else None
    return {k: row.get(k) for k in ('key', 'sessionId', 'sessionStartedAt', 'totalTokens', 'totalTokensFresh')}


def capture(base, run_dir, core_log, pid, sh=sh):
    th = json.loads(urllib.request.urlopen(base + '/api/thread', timeout=30).read())
    try:
        with open(os.path.join(run_dir, 'receipts.jsonl'), 'rb') as f:
            rec = [hashlib.sha256(l).hexdigest() for l in f.read().splitlines()]
    except FileNotFoundError:
        rec = []
    with open(core_log, errors='replace') as f:
        boot = [l.split(':', 1)[1].strip() for l in f if l.startswith('token pushed:')]
    top = sh([*rp.D, 'top', 'oc551-worker', '-o', 'pid,args']) or ''
    w = (th.get('receipt') or {}).get('worker') or {}
    return {'core_pid': (sh(['lsof', '-nP', '-iTCP:8550', '-sTCP:LISTEN', '-t']) or '').strip() or None,
            'token_pushed': boot[-1] if boot else None,
            'containers': sh([*rp.D, 'inspect', '-f', '{{.Name}} {{.Id}} {{.State.StartedAt}} {{.State.Running}}',
                              'oc551-worker', 'oc551-edge']),
            'gateway_pid': next((l.split()[0] for l in top.splitlines()[1:] if 'openclaw' in l and 'gateway' in l), None),
            'thread': th['messages'], 'generation': th['generation'], 'session_key': th['session_key'],
            'active_turn': th.get('active_turn'),
            'last_receipt': {'run_id': w.get('run_id'), 'state': w.get('state')} if th.get('receipt') else None,
            'state': rp.state(run_dir, pid), 'receipts': rec,
            'session': session_row(sh(SESSIONS), th['session_key'])}


def compare(pre, post, turn=None):
    """[(check, True | False | None)]: None is UNKNOWN (manual review), never a PASS."""
    out = []
    check = lambda name, ok: out.append((name, ok))
    last = pre['last_receipt'] if isinstance(pre['last_receipt'], dict) else {}
    check('before: no active turn (active_turn false, not missing)', pre['active_turn'] is False)
    check('before: the last receipt is complete (a run id, no worker state)',
          isinstance(last.get('run_id'), str) and bool(last['run_id']) and 'state' in last and last['state'] is None)
    check('a new core pid', bool(post['core_pid']) and post['core_pid'] != pre['core_pid'])
    check('the new boot printed "token pushed: yes"', post['token_pushed'] == 'yes')
    for c in [post] + ([turn] if turn else []):
        check('worker and edge Id/StartedAt unchanged', bool(pre['containers']) and c['containers'] == pre['containers'])
        check('gateway pid unchanged', bool(pre['gateway_pid']) and c['gateway_pid'] == pre['gateway_pid'])
    for k in ('thread', 'generation', 'session_key', 'state'):
        check(f'{k} served unchanged', post[k] == pre[k])
    check('receipts.jsonl keeps its prefix', post['receipts'][:len(pre['receipts'])] == pre['receipts'])
    ident = lambda r: (r.get('sessionId'), r.get('sessionStartedAt'))
    full = lambda r: all(v not in (None, '') for v in ident(r))
    a, b = pre['session'], post['session']
    if a is None or b is None:
        check('OpenClaw session row readable', None)
    elif not (a and b):
        check('OpenClaw session row present before and after', False)
    elif not (full(a) and full(b)):
        check('sessionId and sessionStartedAt non-empty before and after', None)
    else:
        check('sessionId and sessionStartedAt unchanged', ident(a) == ident(b))
    if turn:
        t, tl = turn['session'], turn['last_receipt'] or {}
        check('the first turn after the restart completed with a new run id',
              tl.get('state') is None and bool(tl.get('run_id')) and tl.get('run_id') != last.get('run_id'))
        check('it ran on the same generation and session key',
              (turn['generation'], turn['session_key']) == (pre['generation'], pre['session_key']))
        check('the thread kept its rows and grew by that turn',
              turn['thread'][:len(pre['thread'])] == pre['thread'] and len(turn['thread']) == len(pre['thread']) + 2)
        if t is None or a is None:
            check('OpenClaw session row readable after the turn', None)
        elif not (a and t):
            check('OpenClaw session row present after the turn', False)
        elif not (full(a) and full(t)):
            check('sessionId and sessionStartedAt non-empty after the turn', None)
        else:
            check('the turn kept the session (same sessionId and sessionStartedAt)', ident(t) == ident(a))
            ta, tb = a.get('totalTokens'), t.get('totalTokens')
            if not (isinstance(ta, int) and isinstance(tb, int)):
                check('totalTokens readable', None)
            elif a.get('totalTokensFresh') is False or t.get('totalTokensFresh') is False:
                check('totalTokens fresh (totalTokensFresh false: a stale snapshot)', None)
            elif tb >= ta:
                check('totalTokens no smaller than before (weak consistency evidence, not proof)', True)
            else:
                check(f'totalTokens fell {ta} -> {tb}: possible compaction; manual review, not a FAIL on its own', None)
    return out


def result(checks, turn=True):
    """PASS only for a full O4 (before, after and the first turn); before and after alone is PARTIAL."""
    oks = [ok for _, ok in checks]
    return 'FAIL' if False in oks else 'UNKNOWN' if None in oks else 'PASS' if turn else 'PARTIAL'


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('capture')
    c.add_argument('out')
    c.add_argument('--core-log', required=True)
    c.add_argument('--persona', default='P01')
    c.add_argument('--base', default='http://127.0.0.1:8550')
    c.add_argument('--run-dir', default=os.path.join(rp.ROOT, 'run'))
    m = sub.add_parser('compare')
    m.add_argument('files', nargs='+')
    a = ap.parse_args()
    if a.cmd == 'capture':
        cap = json.dumps(capture(a.base, a.run_dir, a.core_log, a.persona), indent=1)
        if rp.KEY_SHAPED in cap:
            sys.exit('key-shaped token in the capture; nothing written')
        with open(a.out, 'w') as f:
            f.write(cap + '\n')
        print(f'capture: {a.out}')
        return
    if len(a.files) not in (2, 3):
        print('usage: o4_receipt.py compare PRE.json POST.json [TURN.json]', file=sys.stderr)
        sys.exit(64)   # a usage error, never read as FAIL (1) or UNKNOWN (2)
    caps = [json.load(open(f)) for f in a.files]
    checks = compare(*caps)
    res = result(checks, turn=len(caps) == 3)
    for name, ok in checks:
        print(f"{'ok     ' if ok else 'FAIL   ' if ok is False else 'UNKNOWN'}  {name}")
    print(f'MANUAL   {MANUAL}')
    if any(n.startswith('before:') and ok is False for n, ok in checks):   # SOURCE0158: a checker status, not the agent's
        print('PRECONDITION NOT MET: the capture was not taken idle and complete; this FAIL is a checker status, '
              'not an agent or durability failure')
    print(f'RESULT: {res}' + {'PARTIAL': ' (no first-turn capture: not a full O4)',
                              'PASS': ' (MANUAL pending: the reply read above is not done by this tool)'}.get(res, ''))
    sys.exit({'PASS': 0, 'FAIL': 1, 'UNKNOWN': 2, 'PARTIAL': 3}[res])


if __name__ == '__main__':
    main()
