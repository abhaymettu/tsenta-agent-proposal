#!/bin/bash
# Apply the reviewed config to the REAL worker WITHOUT a restart (551 v48 steps 2-4). The gateway is the container's init
# (entrypoint exec; AutoRemove), so a container restart would delete the tmpfs key. The live config is
# /demo/state/openclaw.json5 (tmpfs, node-writable); OpenClaw's hybrid reload applies agents.defaults.* and tools.* hot
# (config-reload-plan:165, :273), and any other changed path defaults to a restart (:389), so the repo file must differ
# from the live one in exactly those two keys (551 reviewed the diff at 59839ba).
# Second change (operator 22:37, 551 v65): agents.defaults.heartbeat.every "0m" only. agents.defaults.heartbeat is a hot
# path with restartHeartbeat + reconcileSystemJobs (config-reload-plan-j1Dikn28.mjs :186-197): in process, no restart.
# 2 pre-gate: live sha256 == EXPECT_LIVE_SHA (default cdfda745, the config applied at 21:47); the 8550 core is offline (no
#   WORKER_CONTAINER, so no user turn can run); record the gateway pid (docker top), the worker Id/StartedAt, edge
#   api.anthropic.com:443 allowed (must equal EXPECT_API_ALLOWED, default 10: 7 receipted plus heartbeat run 2d01e83a)
# 3 write the repo file over `docker exec -i` stdin to .new, then mv over the live file (atomic for the watcher)
# 4 verify within 15 s (debounce 300 ms): "config change detected; evaluating reload (" then an applied marker, and none of
#   the restart/failure markers, in the worker log since the write (no marker at all = UNKNOWN, STOP, no rewrite);
#   gateway pid, Id and StartedAt unchanged; api allowed unchanged; no new model-fetch log line; live sha == repo
# No key read: only sha256sum and cat of config.sha256 run inside the worker. No model call. Any failure: STOP, no retry.
# Run only on the operator's GO. Usage: openclaw/live-config-apply.sh   (exit 0 PASS, 1 FAIL, 2 UNKNOWN)
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_CFG="$HERE/openclaw.json5"
# reload markers at the pin (551 v49, server-reload-managed-BpRXbVVd.mjs), matched as fixed strings
DETECT='config change detected; evaluating reload ('
APPLIED=('config hot reload applied (' 'config change applied (dynamic reads:')
BAD=('requires gateway restart' 'restarting gateway now' 'restart-required reload rejected' 'config reload skipped (invalid config)'
     'config reload failed' 'config reload superseded' 'config reload skipped by writer intent' 'hot-reload disabled')
fcount() { local n=0 m; for m in "$@"; do n=$(( n + $(printf '%s\n' "$WL" | grep -cF -- "$m") )); done; echo "$n"; }
wlog() { "${D[@]}" logs --since "$T0" oc551-worker 2>&1 | grep -v 'sk-ant-' | sed -E 's/[A-Za-z0-9_\-]{40,}/<redacted>/g'; }
API_EXPECT="${EXPECT_API_ALLOWED:-10}"
LIVE_EXPECT="${EXPECT_LIVE_SHA:-cdfda745f432b5d8ad62babe6dec41e2e4a8e86e7e9671646783256c538eff60}"
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/LIVE-CONFIG-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
wexec() { "${D[@]}" exec -u node oc551-worker "$@"; }
gwpid() { "${D[@]}" top oc551-worker -o pid,args 2>/dev/null | awk 'NR > 1 && /[o]penclaw/ && /gateway/ {print $1; exit}'; }
api() { local l; l=$("${D[@]}" logs oc551-edge 2>&1) || { echo unreadable; return; }
  printf '%s\n' "$l" | python3 -I -c '
import json, sys
n = 0
for line in sys.stdin:
    try: o = json.loads(line)
    except ValueError: continue
    if isinstance(o, dict) and o.get("op") == "CONNECT" and o.get("target") == "api.anthropic.com:443" and o.get("verdict") == "allowed": n += 1
print(n)'; }

say "live config apply $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$HERE/.." rev-parse --short HEAD); repo cfg sha256 $(shasum -a 256 "$REPO_CFG" | cut -c1-16)"
W0=$("${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-worker 2>/dev/null)
check "worker running" "$(echo "$W0" | awk '{print $3}')" true
P0=$(gwpid); check "gateway pid found" "$([[ $P0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes; info "gateway pid" "$P0"
live=$(wexec sha256sum /demo/state/openclaw.json5 2>/dev/null | cut -c1-64)
check "live config sha256 == EXPECT_LIVE_SHA" "$live" "$LIVE_EXPECT"
CP=$(lsof -nP -iTCP:8550 -sTCP:LISTEN -Fp | sed -n 's/^p//p' | head -1)
check "8550 core offline (WORKER_CONTAINER unset)" "$([[ $CP =~ ^[0-9]+$ ]] && ps eww -o command= -p "$CP" | tr ' ' '\n' | grep -c '^WORKER_CONTAINER=')" 0
A0=$(api); check "edge api.anthropic.com:443 allowed before" "$A0" "$API_EXPECT"
check "repo config differs from the live one" "$([ "$(shasum -a 256 "$REPO_CFG" | cut -c1-64)" != "$live" ] && echo yes || echo no)" yes
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (pre-gate; nothing written)"; exit 1; }

T0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"${D[@]}" exec -i -u node oc551-worker sh -c 'umask 077; cat > /demo/state/openclaw.json5.new && mv /demo/state/openclaw.json5.new /demo/state/openclaw.json5' < "$REPO_CFG"
check "write exit" "$?" 0
for _ in $(seq 1 30); do WL=$(wlog); [ "$(fcount "${APPLIED[@]}")" -ge 1 ] || [ "$(fcount "${BAD[@]}")" -ge 1 ] && break; sleep 0.5; done
sleep 1; WL=$(wlog)
check "key-shaped tokens in the worker log since the write (counted, those lines dropped)" "$("${D[@]}" logs --since "$T0" oc551-worker 2>&1 | grep -c 'sk-ant-')" 0
nd=$(fcount "$DETECT"); na=$(fcount "${APPLIED[@]}"); nb=$(fcount "${BAD[@]}")
info "reload evaluation lines (paths)" "$(printf '%s\n' "$WL" | grep -F -- "$DETECT" | sed 's/.*evaluating reload (/(/' | cut -c1-200 | paste -sd'|' -)"
if [ "$nb" -gt 0 ]; then say "FAIL  restart or failure marker since the write: $(printf '%s\n' "$WL" | grep -F -e "${BAD[0]}" -e "${BAD[1]}" -e "${BAD[2]}" -e "${BAD[3]}" -e "${BAD[4]}" -e "${BAD[5]}" -e "${BAD[6]}" -e "${BAD[7]}" | cut -c1-200 | head -3)"; FAILS=$((FAILS + 1))
elif [ "$na" -eq 0 ]; then say "RESULT: UNKNOWN (no reload marker in 15 s). STOP: no rewrite, no restart."; say "receipt: $OUT"; exit 2; fi
check "reload evaluation marker present" "$([ "$nd" -ge 1 ] && echo yes || echo no)" yes
# 551 v50 L-7: the evaluated paths are exactly the reviewed key. A newly added object is reported as its own path
# (collectConfigDiffPaths :12-31), or as its leaf if a refinement prefix covers it; exactly one of the two is accepted.
paths=$(printf '%s\n' "$WL" | grep -F -- "$DETECT" | sed 's/.*evaluating reload (//' | grep -oE '[A-Za-z_]+(\.[A-Za-z_]+)+' | sort -u | paste -sd' ' -)
check "evaluated config paths (agents.defaults.heartbeat[.every] only)" "$([ "$paths" = agents.defaults.heartbeat ] || [ "$paths" = agents.defaults.heartbeat.every ] && echo yes || echo "no: $paths")" yes
ld=$(printf '%s\n' "$WL" | grep -nF -- "$DETECT" | head -1 | cut -d: -f1)
la=$(printf '%s\n' "$WL" | grep -nF -e "${APPLIED[0]}" -e "${APPLIED[1]}" | head -1 | cut -d: -f1)
check "evaluation precedes the applied marker" "$([ -n "$ld" ] && [ -n "$la" ] && [ "$ld" -lt "$la" ] && echo yes || echo no)" yes
info "applied marker" "$(printf '%s\n' "$WL" | grep -F -e "${APPLIED[0]}" -e "${APPLIED[1]}" | head -1 | sed 's/.*\(config [a-z ]*applied\)/\1/' | cut -c1-160)"
check "model-fetch lines since the write" "$(printf '%s\n' "$WL" | grep -cF '[model-fetch]')" 0
check "gateway pid unchanged" "$(gwpid)" "$P0"
check "worker Id StartedAt Running unchanged" "$("${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-worker 2>/dev/null)" "$W0"
check "edge api.anthropic.com:443 allowed unchanged" "$(api)" "$A0"
check "live config == repo" "$(wexec sha256sum /demo/state/openclaw.json5 2>/dev/null | cut -c1-64)" "$(shasum -a 256 "$REPO_CFG" | cut -c1-64)"
info "heartbeat/cron lines since the write" "$(printf '%s\n' "$WL" | grep -iE 'heartbeat|cron' | sed 's/^[^ ]* //' | cut -c1-160 | paste -sd'|' -)"
check "8550 core still offline" "$(ps eww -o command= -p "$CP" | tr ' ' '\n' | grep -c '^WORKER_CONTAINER=')" 0
info "worker log lines since the write (count only)" "$(printf '%s\n' "$WL" | grep -c .)"
say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "next: EXPECT_API_ALLOWED=$API_EXPECT openclaw/real-checks.sh; the edge api count must stay $API_EXPECT past the next due heartbeat"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
