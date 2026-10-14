#!/bin/bash
# Metadata-only checks after the REAL model key fill (551 v13 real-run rules; operator 19:29). Run once the worker and
# the edge are up and the user has filled the key by hand through the fill page.
# This script never reads the key: no cat or tar of /run/secrets, no /proc/*/environ, no value-needle scan, no file sizes.
# It reads only modes and owners, entry names, gateway liveness and health (ok only), cgroup memory counters, docker diff,
# and the edge's own JSON log (allowlist and CONNECT host:port/verdict). Log text is only counted (grep -c), never printed.
# Key-shaped tokens (sk-ant-) in the worker log and the health output are counted by pattern only; any count above 0 FAILs.
# clawhub.ai prewarm: refused, at most 1, reported as info (the parent's engineering choice A, ruled sufficient for REAL by the
# operator at 20:49:50; not a user decision). Non-refused CONNECTs to anything but api.anthropic.com:443, or any op http, FAIL.
# Usage: openclaw/real-checks.sh   (receipt: ~/audit/tsenta-openclaw-1013/REAL-CHECKS-<time>.txt; exit 0 PASS, 1 FAIL)
set -uo pipefail
D=(docker --context desktop-linux)
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/REAL-CHECKS-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
wexec() { "${D[@]}" exec -u node oc551-worker "$@"; }
lcount() { local c="$1" l; shift; l=$("${D[@]}" logs "$c" 2>&1) || { echo unreadable; return; }; printf '%s\n' "$l" | grep -c "$@"; true; }   # 551 RC-1: a failed docker logs is "unreadable", never a 0
labelled() { [ "$("${D[@]}" inspect -f '{{index .Config.Labels "oc551"}}' "$1" 2>/dev/null)" = 1 ]; }

say "real-key metadata checks $(date '+%Y-%m-%dT%H:%M:%S%z'); worker image $("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3 | cut -c8-19); edge image $("${D[@]}" image inspect -f '{{.Id}}' oc551-edge:1 | cut -c8-19)"
for c in oc551-worker oc551-edge; do
  check "$c running and labelled oc551=1" "$(labelled "$c" && "${D[@]}" inspect -f '{{.State.Running}}' "$c")" true
done
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (containers)"; exit 1; }

# the key file: mode and owner only (551: "600 node with no size"); the directory holds exactly the two expected names
check "model_key mode owner" "$(wexec stat -c '%a %U' /run/secrets/model_key 2>/dev/null)" "600 node"
check "/run/secrets entry names" "$(wexec sh -c 'ls -A /run/secrets | sort | paste -sd" " -')" "gateway_token model_key"
check "/run/secrets mode owner" "$(wexec stat -c '%a %U' /run/secrets)" "700 node"

# the gateway: started, ready, alive, healthy (liveness only; it does not prove a working tool agent)
check "entrypoint stage 2 ok; starting gateway (log lines)" "$(lcount oc551-worker 'stage 2 ok; starting gateway')" 1
check "'[gateway] ready' log lines" "$(lcount oc551-worker -E '\[gateway\] ready$')" 1
check "'start blocked' log lines" "$(lcount oc551-worker -i 'start blocked')" 0
check "key-shaped tokens (sk-ant-) in the worker log, counted by pattern" "$(lcount oc551-worker 'sk-ant-')" 0
if procs=$("${D[@]}" top oc551-worker -o pid,args 2>/dev/null); then
  check "docker top shows the openclaw gateway process" "$(printf '%s\n' "$procs" | tail -n +2 | grep -cE '[o]penclaw.*gateway' | awk '{print ($1 > 0) ? "yes" : "no"}')" yes
  check "npm processes in the worker (one sample)" "$(printf '%s\n' "$procs" | tail -n +2 | grep -c '[n]pm')" 0
else say "FAIL  docker top failed"; FAILS=$((FAILS + 1)); fi
hj=$(wexec sh -c 'OPENCLAW_GATEWAY_TOKEN="$(cat /run/secrets/gateway_token)" openclaw health --json --timeout 5000' 2>/dev/null); hrc=$?
check "openclaw health exit" "$hrc" 0
check "openclaw health top-level ok" "$(printf '%s' "$hj" | python3 -I -c 'import json, sys
try: print(json.load(sys.stdin).get("ok") is True)
except Exception: print("unparseable")')" True
check "key-shaped tokens (sk-ant-) in the health output, counted by pattern" "$(printf '%s\n' "$hj" | grep -c 'sk-ant-')" 0; hj=""

# memory: swap stays off; no OOM kill
for c in oc551-worker oc551-edge; do
  check "$c HostConfig Memory == MemorySwap" "$("${D[@]}" inspect -f '{{if eq .HostConfig.Memory .HostConfig.MemorySwap}}equal{{else}}{{.HostConfig.Memory}}/{{.HostConfig.MemorySwap}}{{end}}' "$c")" equal
  check "$c memory.swap.max" "$("${D[@]}" exec "$c" cat /sys/fs/cgroup/memory.swap.max)" 0
  check "$c memory.swap.current" "$("${D[@]}" exec "$c" cat /sys/fs/cgroup/memory.swap.current)" 0
  check "$c memory.events oom_kill" "$("${D[@]}" exec "$c" sh -c 'awk "\$1==\"oom_kill\"{print \$2}" /sys/fs/cgroup/memory.events')" 0
  info "$c memory.peak / memory.max (bytes)" "$("${D[@]}" exec "$c" sh -c 'echo "$(cat /sys/fs/cgroup/memory.peak) / $(cat /sys/fs/cgroup/memory.max)"')"
done

# the worker's root filesystem is unchanged (everything it writes is tmpfs)
if df=$("${D[@]}" diff oc551-worker 2>/dev/null); then check "docker diff worker (root fs changes)" "$(printf '%s' "$df" | grep -c .)" 0
else say "FAIL  docker diff worker: command failed"; FAILS=$((FAILS + 1)); fi
check "worker networks" "$("${D[@]}" inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' oc551-worker | xargs)" oc551-int

# the edge: allowlist exactly the model API; CONNECTs by exact (op, target, verdict) from its JSON log
EL=$("${D[@]}" logs oc551-edge 2>&1) || { say "FAIL  docker logs edge failed"; FAILS=$((FAILS + 1)); EL="unreadable"; }
ej=$(printf '%s\n' "$EL" | python3 -I -c '
import collections, json, sys
allow, conn, http, unp = None, collections.Counter(), 0, 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except ValueError:
        unp += 1; continue
    if not isinstance(o, dict):
        unp += 1; continue
    if "allow" in o and allow is None:
        allow = o["allow"]
    if o.get("op") == "http":
        http += 1
    elif o.get("op") == "CONNECT":
        conn[(o.get("target"), o.get("verdict"))] += 1
# 551 v40 E-4: the Gateway reaches its MCP server through the edge own tool port, so oc551-edge:8560/allowed is expected
bad = sum(n for (t, v), n in conn.items() if v != "refused" and t != "api.anthropic.com:443" and (t, v) != ("oc551-edge:8560", "allowed"))
t8ok = conn[("oc551-edge:8560", "allowed")]
t8bad = sum(n for (t, v), n in conn.items() if t == "oc551-edge:8560" and v == "upstream-error")
api = sum(n for (t, v), n in conn.items() if t == "api.anthropic.com:443" and v == "allowed")
apibad = sum(n for (t, v), n in conn.items() if t == "api.anthropic.com:443" and v != "allowed")
hub = conn[("clawhub.ai:443", "refused")]
print(json.dumps(allow, separators=(",", ":")))
print(bad, http, unp, api, hub, apibad, t8ok, t8bad)
print(" ".join(f"{t}/{v}x{n}" for (t, v), n in sorted(conn.items(), key=str)) or "none")') || { say "FAIL  edge log classifier failed"; FAILS=$((FAILS + 1)); }
{ read -r allow; read -r bad http unp api hub apibad t8ok t8bad; read -r summary; } <<< "$ej"
check "edge allowlist (551 v40: the model API and the edge's own tool port)" "$allow" '["api.anthropic.com:443","oc551-edge:8560"]'
check "edge CONNECTs not refused to anything but api.anthropic.com:443 and oc551-edge:8560" "${bad:-x}" 0
check "edge CONNECTs to oc551-edge:8560 upstream-error" "${t8bad:-x}" 0
info "edge CONNECTs to oc551-edge:8560 allowed (the Gateway's MCP client)" "${t8ok:-x}"
# 551 v28 P1: no agent turn has happened yet, so ANY CONNECT to the model host (allowed by the edge) would be a startup call
# carrying the key (e.g. model discovery, which models.mode replace turns off). It must be 0 here.
# 551 v36 P-6: after the routed 9.5 step 2 ping, EXPECT_API_ALLOWED is the ping's allowed delta; unset means no ping yet (0).
check "edge CONNECTs to api.anthropic.com:443 allowed (expected ${EXPECT_API_ALLOWED:-0}: ${EXPECT_API_ALLOWED:+the 9.5 step 2 ping}${EXPECT_API_ALLOWED:-no turn yet})" "${api:-x}" "${EXPECT_API_ALLOWED:-0}"
check "edge CONNECTs to api.anthropic.com:443 refused or upstream-error" "${apibad:-x}" 0
if [ "${hub:-x}" = 0 ] || [ "${hub:-x}" = 1 ]; then info "edge clawhub.ai:443 refused (post-start plugin-feed prewarm; at most 1)" "$hub"
else say "FAIL  edge clawhub.ai:443 refused = ${hub:-x} (want at most 1)"; FAILS=$((FAILS + 1)); fi
check "edge plain-http requests" "${http:-x}" 0
check "edge log lines that are not JSON objects" "${unp:-x}" 0
info "edge CONNECTs (host:port/verdict x count; clawhub.ai refused under the parent's engineering choice A, settled by the operator 20:49:50; not a user decision)" "${summary:-none}"

say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
