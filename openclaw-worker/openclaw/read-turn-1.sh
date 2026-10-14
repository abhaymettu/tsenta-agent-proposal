#!/bin/bash
# The first REAL tool turn (operator 21:57): ONE read-only user message as the fictional persona P01 (Riley Quinn),
# through the core's own /api/message route, so the production path runs end to end: core -> Worker.run_turn (task over
# stdin to /demo/io/task.md, then the fixed agent-turn.sh with the session key) -> the Gateway's agent run -> the model ->
# MCP tools/call through the edge's tool forward -> this core's fixture tools -> the reply.
# Precondition (a separate step on its own GO): the core restarted with WORKER_CONTAINER=oc551-worker (core-only; no
# container is touched). The message asks for status counts only and says not to change anything.
# PASS needs all of:
#  memory    worker memory.current < 1.6 GiB before (else nothing is sent); oom_kill delta 0 (551 v57 M-1)
#  core      worker configured; session key tsenta-demo-g2-P01; receipt worker.run_id set, no offline/unknown state;
#            1 to 6 tool events, every one a read tool and accepted (status_summary is info); receipt sandbox_log []
#  effects   core events delta == 1 user + the tool events; sandbox.db row counts unchanged (read-only open); no new
#            receipts besides this one
#  edge      api.anthropic.com:443 allowed delta >= 1, refused 0, other 0; tool forwarded 200 delta >= tool events;
#            8560 not-allowed new 0
#  gateway   "[agent] run <runId> ended" in the worker log since T0; [model-fetch] >= 1; "Activity summary" 0; sk-ant- 0
#  reply     non-empty, no key-shaped token; says 7 applications (info: the fixture answer is 7, one in each of 7 statuses)
#  state     worker and edge Id/StartedAt unchanged
# Timeout or no answer: UNKNOWN (exit 2), never retried. Any FAIL: STOP. Usage: openclaw/read-turn-1.sh  (0 PASS, 1 FAIL, 2 UNKNOWN)
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/.."
TEXT='How many of my job applications are in each status right now? Only look this up. Do not save, draft, request approval, submit or send anything.'
READ_TOOLS=" profile_get status_summary record_search record_get mail_list mail_read "
API_BEFORE="${EXPECT_API_BEFORE:?cumulative edge api.anthropic.com:443 allowed before the turn (5 after the 21:52 ping)}"
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/READ-TURN-1-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
state() { "${D[@]}" inspect -f '{{.Name}} {{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-worker oc551-edge 2>/dev/null || echo missing; }
status() { python3 -I -c 'import json, urllib.request; d = json.load(urllib.request.urlopen("http://127.0.0.1:8550/api/status", timeout=5)); print(d["worker"]["state"], d["worker"].get("container"), d["session_key"], d["persona"]["id"])' 2>/dev/null || echo unreachable; }
events() { python3 -I -c 'import sqlite3, sys; c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True); print(c.execute("SELECT count(*) FROM events").fetchone()[0])' "$ROOT/run/core.db" 2>/dev/null || echo unreadable; }
boxrows() { python3 -I -c '
import sqlite3, sys
c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
print(" ".join("%s=%d" % (t, c.execute("SELECT count(*) FROM \"%s\"" % t).fetchone()[0]) for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type = \"table\" ORDER BY name")))' "$ROOT/run/sandbox.db" 2>/dev/null || echo unreadable; }
oom() { "${D[@]}" exec -u node oc551-worker sh -c 'sed -n "s/^oom_kill //p" /sys/fs/cgroup/memory.events' 2>/dev/null; }
edge() {  # api_allowed api_bad other t8_bad tool_200
  local l; l=$("${D[@]}" logs oc551-edge 2>&1) || { echo unreadable; return; }
  printf '%s\n' "$l" | python3 -I -c '
import json, sys
a = b = o = f = g = 0
for line in sys.stdin:
    try: x = json.loads(line)
    except ValueError: continue
    if not isinstance(x, dict): continue
    op, tg, v = x.get("op"), x.get("target"), x.get("verdict")
    if op == "CONNECT" and tg == "api.anthropic.com:443":
        if v == "allowed": a += 1
        else: b += 1
    elif op == "CONNECT" and tg == "oc551-edge:8560":
        if v != "allowed": f += 1
    elif op == "CONNECT" and tg != "clawhub.ai:443": o += 1
    if op == "tool" and v == "forwarded" and x.get("status") == 200: g += 1
print(a, b, o, f, g)'
}

say "read turn 1 $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$ROOT" rev-parse --short HEAD); text sha256 $(printf '%s' "$TEXT" | shasum -a 256 | cut -c1-16)"
BEFORE=$(state)
check "real containers running" "$(printf '%s\n' "$BEFORE" | awk '$4 == "true"' | wc -l | tr -d ' ')" 2
check "core worker state, container, session key, persona" "$(status)" "configured oc551-worker tsenta-demo-g2-P01 P01"
read -r a0 b0 o0 f0 g0 <<< "$(edge)"
check "edge api.anthropic.com:443 allowed before" "$a0" "$API_BEFORE"
check "edge api.anthropic.com:443 refused or upstream-error before" "$b0" 0
# 551 v57 M-1: an OOM kill ends the container, and --rm takes the tmpfs key with it; stop before sending if memory is high
mem=$("${D[@]}" exec -u node oc551-worker cat /sys/fs/cgroup/memory.current 2>/dev/null); oom0=$(oom); info "worker memory.current (bytes)" "$mem"
check "worker memory.current < 1.6 GiB" "$([[ $mem =~ ^[0-9]+$ ]] && [ "$mem" -lt 1717986918 ] && echo yes || echo no)" yes
check "worker oom_kill readable" "$([[ $oom0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes
ev0=$(events); bx0=$(boxrows); rc0=$(wc -l < "$ROOT/run/receipts.jsonl" | tr -d ' ')
check "core events readable" "$([[ $ev0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes
check "sandbox.db readable (read-only)" "$([ "$bx0" != unreadable ] && echo yes || echo no)" yes
info "sandbox.db rows before" "$bx0"
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (preconditions; no message sent)"; exit 1; }

umask 077; RES=$(mktemp "${TMPDIR:-/tmp}/turn1.XXXXXX"); trap 'rm -f "$RES"' EXIT
T0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
python3 -I -c '
import json, sys, urllib.request
req = urllib.request.Request("http://127.0.0.1:8550/api/message", data=json.dumps({"text": sys.argv[1]}).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
open(sys.argv[2], "wb").write(urllib.request.urlopen(req, timeout=700).read())' "$TEXT" "$RES" 2>/dev/null
prc=$?
if [ "$prc" -ne 0 ] || [ ! -s "$RES" ]; then
  say "RESULT: UNKNOWN (no answer from /api/message, exit $prc). The Gateway run may still be going. STOP: no retry."; say "receipt: $OUT"; exit 2; fi
check "key-shaped tokens (sk-ant-) in the /api/message answer" "$(grep -c 'sk-ant-' "$RES")" 0
sum=$(python3 -I -c '
import json, re, sys
r = json.load(open(sys.argv[1]))["receipt"]; w = r.get("worker") or {}
tools = [e for e in r.get("tools") or [] if isinstance(e, dict)]   # engine.turn_events: flat {tool, decision, ...}
names = [e.get("tool") for e in tools]; dec = [e.get("decision") for e in tools]
print("state", w.get("state") or "ok"); print("runid", w.get("run_id") if isinstance(w.get("run_id"), str) and re.fullmatch(r"[A-Za-z0-9-]{1,80}", w["run_id"]) else "bad")
print("sk", w.get("session_key")); print("model", w.get("model")); print("usage", json.dumps(w.get("usage"))[:200])
print("ntools", len(tools)); print("names", ",".join(map(str, names)) or "none"); print("decisions", ",".join(map(str, dec)) or "none")
print("sandboxlog", len(r.get("sandbox_log") or [])); print("direct", r.get("direct_model_calls"))
m = [x for x in json.load(open(sys.argv[1])).get("messages", []) if x.get("turn") == r.get("turn") and x.get("who") == "them"]
t = m[-1]["text"] if m else ""; print("replylen", len(t.strip())); print("reply7", "yes" if re.search(r"\b(7|seven)\b", t, re.I) else "no")
print("reply", repr(t.strip()[:300]))' "$RES" 2>&1)
v() { printf '%s\n' "$sum" | sed -n "s/^$1 //p" | head -1; }
st=$(v state); [ "$st" = unknown ] && { say "RESULT: UNKNOWN (receipt worker state unknown: the turn timed out). STOP: no retry."; say "receipt: $OUT"; exit 2; }
check "receipt worker state" "$st" ok
check "receipt run_id an id string" "$([ "$(v runid)" != bad ] && echo yes || echo no)" yes
check "receipt session key" "$(v sk)" tsenta-demo-g2-P01
check "receipt direct model calls" "$(v direct)" 0
NT=$(v ntools); info "tools called (in order)" "$(v names)"; info "decisions" "$(v decisions)"
check "tool events 1 to 6" "$([[ $NT =~ ^[0-9]+$ ]] && [ "$NT" -ge 1 ] && [ "$NT" -le 6 ] && echo yes || echo "no ($NT)")" yes
bad=0; for n in $(v names | tr ',' ' '); do [[ $READ_TOOLS == *" $n "* ]] || bad=$((bad + 1)); done
check "tool events that are not read tools" "$bad" 0
check "tool events not accepted" "$(v decisions | tr ',' '\n' | grep -vc '^accepted$')" 0
info "status_summary called (551 v57 R-2: record_search can answer too)" "$(v names | tr ',' '\n' | grep -c '^status_summary$')"
check "receipt sandbox_log entries" "$(v sandboxlog)" 0
check "reply non-empty" "$([ "$(v replylen)" -gt 0 ] 2>/dev/null && echo yes || echo no)" yes
info "reply says 7 applications (fixture: 7 total, one each of interview, rejected, on_hold, quiet, unconfirmed, interview_cancelled, assessment)" "$(v reply7)"
info "reply (first 300 characters)" "$(v reply)"; info "model" "$(v model)"; info "usage" "$(v usage)"
sleep 5   # a late background call would log here
RUNID=$(v runid)
read -r a1 b1 o1 f1 g1 <<< "$(edge)"
if [[ $a1 =~ ^[0-9]+$ ]]; then
  DELTA=$(( a1 - a0 )); info "edge api.anthropic.com:443 allowed delta" "$DELTA"
  check "edge api.anthropic.com:443 allowed during the turn (routed)" "$([ "$DELTA" -ge 1 ] && echo yes || echo no)" yes
  check "edge api.anthropic.com:443 refused or upstream-error (new)" "$(( b1 - b0 ))" 0
  check "edge other new CONNECTs" "$(( o1 - o0 ))" 0
  check "edge CONNECT oc551-edge:8560 not allowed (new)" "$(( f1 - f0 ))" 0
  # 551 v57 R-1: the Gateway's MCP client may also POST tools/list or re-initialize per run, so >= the tool events
  info "edge tool forwarded 200 delta / tool events" "$(( g1 - g0 )) / $NT"
  check "edge tool forwarded 200 delta >= tool events" "$([ $(( g1 - g0 )) -ge "${NT:-0}" ] && echo yes || echo no)" yes
else check "edge log readable after" no yes; fi
L=$("${D[@]}" logs --since "$T0" oc551-worker 2>&1)
check "key-shaped tokens (sk-ant-) in the worker log since T0" "$(printf '%s\n' "$L" | grep -c 'sk-ant-')" 0
check "worker log: [agent] run <runId> ended" "$([[ $RUNID =~ ^[A-Za-z0-9-]+$ ]] && printf '%s\n' "$L" | grep -v 'sk-ant-' | grep -qF "[agent] run $RUNID ended" && echo yes || echo no)" yes
mf=$(printf '%s\n' "$L" | grep -c '\[model-fetch\] response'); info "worker model-fetch responses since T0" "$mf"
check "worker model-fetch responses >= 1" "$([ "$mf" -ge 1 ] && echo yes || echo no)" yes
check "worker log 'Activity summary' lines since T0" "$(printf '%s\n' "$L" | grep -ci 'activity summary')" 0
ev1=$(events)
check "core events delta == 1 user + tool events" "$([[ $ev1 =~ ^[0-9]+$ ]] && echo $(( ev1 - ev0 )) || echo unreadable)" "$(( 1 + ${NT:-0} ))"
check "sandbox.db rows unchanged" "$(boxrows)" "$bx0"
check "new receipts (this turn only)" "$(( $(wc -l < "$ROOT/run/receipts.jsonl" | tr -d ' ') - rc0 ))" 1
check "worker oom_kill delta" "$(( $(oom || echo 999) - oom0 ))" 0
info "worker memory.current after (bytes)" "$("${D[@]}" exec -u node oc551-worker cat /sys/fs/cgroup/memory.current 2>/dev/null)"
check "worker and edge Id StartedAt unchanged" "$([ "$BEFORE" = "$(state)" ] && echo yes || echo changed)" yes
say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "next: EXPECT_API_ALLOWED=$(( API_BEFORE + ${DELTA:-0} )) openclaw/real-checks.sh; then the core back to offline (restart without WORKER_CONTAINER) unless the operator rules otherwise"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
