#!/bin/bash
# Restart ONLY the REAL edge with the allowlist extended by its own tool port (551 v40 option A). Inside the Gateway the
# proxy routes every fetch, the bundle-mcp client included (network-proxy.md:70), so the MCP call to oc551-edge:8560 arrives
# as CONNECT oc551-edge:8560; the tunnel lands on the edge's own POST /mcp forward, which adds the bearer. No new reach; the
# edge holds no key, and the worker (with the key) is not touched.
# E-3: `EDGE_ALLOW=api.anthropic.com:443,oc551-edge:8560 phase1.sh edge` (the edge branch only); the worker's Id and
#      StartedAt must be identical before and after, and it must stay running.
# The edge's own name resolves to both of its networks inside it (/etc/hosts), so the edge dials oc551-edge:8560 at its bind
# address (edge.mjs edgeConnect, 551 v43 A1); the in-edge DNS equality (E-1) is dropped. ER-2: from the worker, oc551-edge
# must resolve to the edge's int IP only (that is where the Gateway dials 3128).
# Records edge_id= / edge_started= / edge_image= in the receipt; ping-95.sh reads them from there.
# E-2 (the core-only restart that re-pushes the bearer, lost with the old edge's tmpfs) is a separate step after this.
# Run only on the operator's GO. Usage: openclaw/edge-restart.sh <reviewed edge digest prefix>   (exit 0 PASS, 1 FAIL)
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
ALLOW=api.anthropic.com:443,oc551-edge:8560
E_EXPECT="${1:?reviewed edge digest prefix (from the A1 build)}"
[[ $E_EXPECT =~ ^[0-9a-f]{16,}$ ]] || { echo "refusing: digest prefix must be at least 16 hex characters" >&2; exit 2; }   # 551 v44 D-1
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/EDGE-RESTART-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
winfo() { "${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-worker 2>/dev/null || echo missing; }

say "edge-only restart $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$HERE/.." rev-parse --short HEAD); EDGE_ALLOW=$ALLOW"
W0=$(winfo)
check "worker running before" "$(echo "$W0" | awk '{print $3}')" true
EIMG=$("${D[@]}" image inspect -f '{{.Id}}' oc551-edge:1 | cut -c8-)
check "edge image is the reviewed digest" "$([[ $EIMG == "$E_EXPECT"* ]] && echo yes || echo "no (${EIMG:0:16})")" yes
check "edge labelled oc551=1 before" "$("${D[@]}" inspect -f '{{index .Config.Labels "oc551"}}' oc551-edge 2>/dev/null)" 1
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (preconditions; nothing restarted)"; exit 1; }
say "info  old edge $("${D[@]}" inspect -f '{{.Id}} {{.State.StartedAt}}' oc551-edge | cut -c1-12)"
# the old edge runs with --rm, so its log goes with it: account for every line here first (operator 21:21: all prior
# refusals accounted, nothing filtered). op/target/verdict/status counts only.
old=$("${D[@]}" logs oc551-edge 2>&1) || { say "FAIL  old edge log unreadable; nothing restarted"; exit 1; }
printf '%s\n' "$old" | python3 -I -c '
import collections, json, sys
c = collections.Counter()
for line in sys.stdin:
    if not line.strip(): continue
    try: o = json.loads(line)
    except ValueError: c["non-JSON line"] += 1; continue
    if not isinstance(o, dict): c["non-object line"] += 1; continue
    c[" ".join(str(o.get(k)) for k in ("op", "target", "verdict", "status", "reason", "method", "path") if k in o)] += 1
for k, v in sorted(c.items()): print("old-edge  %3d  %s" % (v, k))' | tee -a "$OUT"
[ "${PIPESTATUS[1]}" = 0 ] || { say "FAIL  old edge log summary failed; nothing restarted"; exit 1; }   # 551 v42 ER-4
grep -q '^old-edge' "$OUT" || { say "FAIL  old edge log summary is empty; nothing restarted"; exit 1; }

EDGE_ALLOW="$ALLOW" "$HERE/phase1.sh" edge 2>&1 | sed 's/^/phase1  /' | tee -a "$OUT"; rc=${PIPESTATUS[0]}   # 551 v41 ER-3
check "phase1.sh edge exit" "$rc" 0
check "worker Id StartedAt Running unchanged" "$(winfo)" "$W0"
check "edge running and labelled oc551=1" "$("${D[@]}" inspect -f '{{.State.Running}} {{index .Config.Labels "oc551"}}' oc551-edge 2>/dev/null)" "true 1"
allow=$("${D[@]}" logs oc551-edge 2>&1 | python3 -I -c '
import json, sys
for line in sys.stdin:
    try: o = json.loads(line)
    except ValueError: continue
    if isinstance(o, dict) and "allow" in o: print(json.dumps(o["allow"], separators=(",", ":"))); break')
check "edge allowlist" "$allow" '["api.anthropic.com:443","oc551-edge:8560"]'
INT=$("${D[@]}" inspect -f '{{(index .NetworkSettings.Networks "oc551-int").IPAddress}}' oc551-edge 2>/dev/null)
check "edge networks" "$("${D[@]}" inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' oc551-edge | xargs)" "oc551-ext oc551-int"
check "edge int IP" "$([[ $INT =~ ^[0-9]+(\.[0-9]+){3}$ ]] && echo yes || echo no)" yes   # 551 v41 ER-1: "" = "" must not pass E-1
check "edge container runs the reviewed image" "$("${D[@]}" inspect -f '{{.Image}}' oc551-edge | cut -c8-)" "$EIMG"
# 551 v41 ER-2: the Gateway dials oc551-edge:3128 from the worker; the exec'd node process there holds no key (read-only lookup)
wres=$("${D[@]}" exec -u node oc551-worker node -e "require('dns').lookup('oc551-edge',{all:true},(e,a)=>console.log(e?e.code:a.map(x=>x.address).sort().join(' ')))" 2>&1)
say "info  oc551-edge resolves (inside the worker) to: $wres"
check "ER-2 every address oc551-edge resolves to inside the worker equals the int IP" "$wres" "$INT"
say "edge_id=$("${D[@]}" inspect -f '{{.Id}}' oc551-edge)"
say "edge_started=$("${D[@]}" inspect -f '{{.State.StartedAt}}' oc551-edge)"
say "edge_image=${EIMG:0:16}"
say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "next: core-only restart (E-2: token pushed: yes, test -s), then openclaw/t1-tunnel.sh, then real-checks"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
