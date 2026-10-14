#!/bin/bash
# 9.5 step 2: ONE routed model ping through the REAL worker's Gateway (contract 9.5; 551 v35 plan in
# OPENCLAW-PRECANARY-REVIEW.md). Run ONLY on its own operator GO, after 551's review, the core-only restart,
# tools-check --pre-session PASS and real-checks PASS. No task turn: WORKER_CONTAINER stays unset in the core, and the core
# refuses tools/call outside an active user turn, so the ping cannot cause a tool side effect. No retry, no reset.
# 1. Pre-checks: the real containers' Id and StartedAt equal the real-fill values below; image prefixes; edge
#    api.anthropic.com:443 CONNECTs = 0; the core reports worker offline; the image copy of agent-turn.sh has no --local
#    and no "agent exec".
# 2. Task, exact, over `docker exec -i` STDIN into /demo/io/task.md (tmpfs); never argv.
# 3. Turn: the image's fixed /opt/demo/agent-turn.sh with session key tsenta-demo-g0-P95 (P95 is no persona, so no core
#    session ever uses this key), under perl alarm 660 (macOS has no timeout(1)). A timeout means UNKNOWN: stop, no retry.
#    The output goes to a 0600 scratch file that is deleted at exit.
# 4. PASS: exit 0; key-shaped tokens 0 (else FAIL and nothing from the output is used); one JSON object; origin gateway;
#    status ok or completed; a non-empty reply; edge delta api.anthropic.com:443 allowed >= 1 (THE step 2 pass), api refused
#    or upstream-error 0, other new CONNECTs 0, http 0, non-JSON 0; tool ops info; no new core event (an accepted tool
#    call would write one). Then: real-checks.sh with EXPECT_API_ALLOWED=<delta>.
# Usage: openclaw/ping-95.sh   |   openclaw/ping-95.sh --selftest   (exit 0 PASS, 1 FAIL, 2 UNKNOWN)
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
KEY=tsenta-demo-g0-P95
TASK='Reply with exactly one word: pong. Do not call any tools.'
W_ID=6d94601557fc08c52926e7bfbc02c5b2596db06e2f76578df89113a284d73540; W_AT=2026-10-14T01:50:53.237535466Z   # real fill
# the edge was restarted with the tool port allowlisted (551 v40 E-3); its Id and StartedAt come from the newest PASS receipt
ER=$(grep -l '^RESULT: PASS' "${TSENTA_AUDIT_DIR:-$PWD/run/audit}"/EDGE-RESTART-*.txt 2>/dev/null | sort | tail -1)
E_ID=$([ -n "$ER" ] && sed -n 's/^edge_id=//p' "$ER"); E_AT=$([ -n "$ER" ] && sed -n 's/^edge_started=//p' "$ER")
W_IMG=e1a9543d1bcf7a06; E_IMG=$([ -n "$ER" ] && sed -n 's/^edge_image=//p' "$ER")   # the A1 edge build, from the receipt
EVENTS_DB="$HERE/../run/core.db"
if [ "${1:-}" = --selftest ]; then
  n=$(grep -vE '^\s*#' "$0" | grep -c 'openclaw[ ]agent'); true   # the turn is the image's agent-turn.sh, never a direct CLI call
  [ "$n" = 0 ] || { echo "selftest FAIL: $n lines call the CLI agent command directly"; exit 1; }
  n=$(grep -vE '^\s*#' "$0" | grep -cE '(^|[^a-z-])(stop|kill|restart|cp)([^a-z]|$).*oc551-(worker|edge)([^:a-z-]|$)'); true
  [ "$n" = 0 ] || { echo "selftest FAIL: $n lines with a forbidden verb next to a real container"; exit 1; }
  echo "selftest PASS"; exit 0
fi
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/PING-95-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
umask 077; RES=$(mktemp "${TMPDIR:-/tmp}/ping95.XXXXXX"); ERR=$(mktemp "${TMPDIR:-/tmp}/ping95e.XXXXXX"); trap 'rm -f "$RES" "$ERR"' EXIT   # 551 v36 P-2
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
edge() {  # api_allowed api_bad other_connect http nonjson tool_ops clawhub_refused t8_allowed t8_bad tool_200   (or "unreadable")
  local l; l=$("${D[@]}" logs oc551-edge 2>&1) || { echo unreadable; return; }
  printf '%s\n' "$l" | python3 -I -c '
import json, sys
a = b = o = h = u = t = c = e = f = g = 0
for line in sys.stdin:
    if not line.strip(): continue
    try: x = json.loads(line)
    except ValueError: u += 1; continue
    if not isinstance(x, dict): u += 1; continue
    op, tg, v = x.get("op"), x.get("target"), x.get("verdict")
    if op == "CONNECT" and tg == "api.anthropic.com:443":
        a += v == "allowed"; b += v != "allowed"
    elif op == "CONNECT" and tg == "oc551-edge:8560":
        e += v == "allowed"; f += v != "allowed"
    elif op == "CONNECT" and tg == "clawhub.ai:443" and v == "refused": c += 1
    elif op == "CONNECT": o += 1
    elif op == "http": h += 1
    elif op == "tool":
        t += 1; g += v == "forwarded" and x.get("status") == 200
print(a, b, o, h, u, t, c, e, f, g)'
}
events() { python3 -I -c 'import sqlite3, sys; c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True); print(c.execute("SELECT count(*) FROM events").fetchone()[0])' "$EVENTS_DB" 2>/dev/null || echo unreadable; }
core_worker() { python3 -I -c 'import json, urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8550/api/status", timeout=5))["worker"]["state"])' 2>/dev/null || echo unreachable; }

say "9.5 step 2 routed ping $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$HERE/.." rev-parse --short HEAD); session key $KEY"
check "edge Id and StartedAt read from an EDGE-RESTART PASS receipt" "$([ -n "$E_ID" ] && [ -n "$E_AT" ] && echo yes || echo no)" yes
say "info  edge receipt: ${ER:-none}"
check "worker Id StartedAt Running = real fill" "$("${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-worker 2>/dev/null)" "$W_ID $W_AT true"
check "edge Id StartedAt Running = edge-restart receipt" "$("${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-edge 2>/dev/null)" "$E_ID $E_AT true"
check "worker image prefix" "$("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3 | cut -c8-23)" "$W_IMG"
check "edge image prefix" "$("${D[@]}" image inspect -f '{{.Id}}' oc551-edge:1 | cut -c8-23)" "$E_IMG"
read -r a0 b0 o0 h0 u0 t0 c0 e0 f0 g0 <<< "$(edge)"
check "edge log readable before" "$([[ $a0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes   # 551 v37 Q-1: unreadable must not pass as 0
# the 21:31 ping left 2 allowed CONNECTs on this edge; EXPECT_API_BEFORE is that cumulative count (551 v48 step 6)
check "edge CONNECTs to api.anthropic.com:443 allowed before" "$a0" "${EXPECT_API_BEFORE:-0}"
check "edge CONNECTs to api.anthropic.com:443 refused or upstream-error before" "$b0" 0
check "core worker state" "$(core_worker)" offline
ts=$("${D[@]}" exec -u node oc551-worker cat /opt/demo/agent-turn.sh 2>/dev/null) || ts=unreadable
check "image agent-turn.sh readable" "$([ "$ts" != unreadable ] && echo yes || echo no)" yes
check "image agent-turn.sh lines with --local or agent exec" "$(printf '%s\n' "$ts" | grep -cE -- '--local|agent exec')" 0
ev0=$(events); info "core events before" "$ev0"
check "core events count readable before" "$([[ $ev0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes   # 551 v37 Q-2
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (pre-checks; no ping sent)"; exit 1; }

printf '%s\n' "$TASK" | "${D[@]}" exec -i -u node oc551-worker sh -c 'umask 077; cat > /demo/io/task.md' || { say "FAIL  could not write /demo/io/task.md; no ping sent"; exit 1; }
T0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
perl -e 'alarm 660; exec @ARGV' "${D[@]}" exec -u node oc551-worker /opt/demo/agent-turn.sh "$KEY" > "$RES" 2> "$ERR"; rc=$?
unknown() { say "RESULT: UNKNOWN ($1; the Gateway run may continue). No retry."; say "receipt: $OUT"; exit 2; }   # 551 v36 P-3
[ "$rc" = 142 ] || [ "$rc" = 124 ] && unknown "turn timed out, exit $rc"
check "turn exit" "$rc" 0
kc=$(( $(grep -c 'sk-ant-' "$RES") + $(grep -c 'sk-ant-' "$ERR") )); true
info "turn stderr lines (not parsed, not printed)" "$(grep -c . "$ERR")"
check "key-shaped tokens (sk-ant-) in the turn output, counted by pattern" "$kc" 0
if [ "$kc" = 0 ]; then
  sum=$(python3 -I -c '
import json, re, sys
s = open(sys.argv[1]).read().strip()
try: d = json.loads(s)
except Exception: print("objects not-one-json-object"); sys.exit()
if not isinstance(d, dict): print("objects not-an-object"); sys.exit()
r = d.get("result") if isinstance(d.get("result"), dict) else {}
txt = "".join(p.get("text", "") for p in r.get("payloads") or [] if isinstance(p, dict) and isinstance(p.get("text"), str))
m = r.get("meta") if isinstance(r.get("meta"), dict) else {}
am = m.get("agentMeta") if isinstance(m.get("agentMeta"), dict) else {}
u = am.get("usage") if isinstance(am.get("usage"), dict) else {}
o = d["origin"] if "origin" in d else "absent"
rid = d.get("runId")
print("objects 1"); print("origin", o if isinstance(o, str) else "non-string"); print("status", d.get("status")); print("runId", rid)
print("runidok", "yes" if isinstance(rid, str) and re.fullmatch(r"[A-Za-z0-9-]{1,80}", rid) else "no"); print("resultobj", "yes" if isinstance(d.get("result"), dict) else "no")
print("replylen", len(txt.strip())); print("reply", repr(txt.strip()[:40]))
print("model", am.get("model") or "not reported"); print("usage", " ".join("%s=%s" % (k, v) for k, v in u.items() if isinstance(v, (int, float))) or "not reported")' "$RES")
  v() { printf '%s\n' "$sum" | sed -n "s/^$1 //p" | head -1; }
  check "turn output is one JSON object" "$(v objects)" 1
  # 551 v55: the pin attaches origin "gateway" only on a failed Gateway run; a success has none. Any other value FAILs.
  og=$(v origin); check "result origin absent or gateway" "$([[ $og == absent || $og == gateway ]] && echo yes || echo "no ($og)")" yes
  check "runId a non-empty id string" "$(v runidok)" yes
  check "result is an object" "$(v resultobj)" yes
  RUNID=$(v runId)
  st=$(v status); [ "$st" = timeout ] && unknown "result status timeout"
  case "$st" in ok|completed) check "result status ok or completed" yes yes ;; *) check "result status ok or completed" "${st:-none}" "ok|completed" ;; esac
  check "reply non-empty" "$([ "$(v replylen)" -gt 0 ] 2>/dev/null && echo yes || echo no)" yes
  info "runId" "$(v runId)"; info "reply length / first 40 characters" "$(v replylen) / $(v reply)"; info "model" "$(v model)"; info "usage" "$(v usage)"
else say "FAIL  key-shaped output: nothing from the turn output is used"; fi
sleep 1
read -r a1 b1 o1 h1 u1 t1 c1 e1 f1 g1 <<< "$(edge)"
if [ "${a1:-unreadable}" = unreadable ]; then check "edge log readable" no yes; else
  DELTA=$(( a1 - a0 ))
  check "9.5 step 2: edge CONNECT api.anthropic.com:443 allowed during the ping (routed)" "$([ "$DELTA" -ge 1 ] && echo yes || echo "no ($DELTA)")" yes
  info "edge api.anthropic.com:443 allowed delta" "$DELTA"
  check "edge api.anthropic.com:443 refused or upstream-error (new)" "$(( b1 - b0 ))" 0
  check "edge other new CONNECTs" "$(( o1 - o0 ))" 0
  check "edge plain-http requests" "$h1" 0
  check "edge non-JSON log lines" "$u1" 0
  info "edge tool ops during the ping" "$(( t1 - t0 ))"
  # 551 v55: a warm Gateway reuses its MCP session, so the deltas are info; it must have reached the MCP server at some point
  info "edge CONNECT oc551-edge:8560 allowed during the ping (0 when the MCP session is warm)" "$(( e1 - e0 ))"
  check "edge CONNECT oc551-edge:8560 allowed, cumulative (the Gateway reached its MCP server, 551 v40)" "$([ "$e1" -ge 1 ] && echo yes || echo "no ($e1)")" yes
  check "edge CONNECT oc551-edge:8560 not allowed (refused or upstream-error, new)" "$(( f1 - f0 ))" 0
  info "edge tool forwarded with status 200 during the ping (0 when warm and the prompt is tool-free)" "$(( g1 - g0 ))"
  check "edge clawhub.ai:443 refused during the ping (551 v36 P-5)" "$(( c1 - c0 ))" 0
  info "edge clawhub.ai:443 refused, cumulative" "$c1"
fi
sleep 5   # a late background call would log here; utilityModel "" should leave none
mf=$("${D[@]}" logs --since "$T0" oc551-worker 2>&1 | grep -c '\[model-fetch\] response'); true
info "worker model-fetch responses since the turn started" "$mf"
# 551 v55 runtime proof: the run ended inside the Gateway (its log is PID 1's output); runId was checked to be [A-Za-z0-9-]
check "worker log: [agent] run <runId> ended (the run was in the Gateway)" "$([[ ${RUNID:-} =~ ^[A-Za-z0-9-]+$ ]] && "${D[@]}" logs --since "$T0" oc551-worker 2>&1 | grep -v 'sk-ant-' | grep -qF "[agent] run $RUNID ended" && echo yes || echo no)" yes
check "worker model-fetch responses: at least the turn's own" "$([ "$mf" -ge 1 ] && echo yes || echo "no ($mf)")" yes
info "model-fetch responses vs routed CONNECTs (one tunnel can carry several requests, 551 v50 P-7)" "$mf / ${DELTA:-?}"
ev1=$(events)
check "new core events (an accepted tool call writes one)" "$([ "$ev0" != unreadable ] && [ "$ev1" != unreadable ] && echo $(( ev1 - ev0 )) || echo unreadable)" 0
check "worker and edge Id StartedAt unchanged" "$("${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}}' oc551-worker oc551-edge | paste -sd' ' -)" "$W_ID $W_AT $E_ID $E_AT"
say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "next: EXPECT_API_ALLOWED=$(( ${EXPECT_API_BEFORE:-0} + ${DELTA:-0} )) openclaw/real-checks.sh (cumulative), then openclaw/tools-check.sh --post-ping"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
