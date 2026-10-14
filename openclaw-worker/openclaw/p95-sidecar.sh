#!/bin/bash
# 9.5 steps 3 and 4 beside the REAL worker, without touching it (551 v31). A keyless sidecar, oc551-p95 (label oc551p95=1,
# NOT oc551=1), runs the reviewed worker image by digest on the LIVE oc551-int network: read-only, cap-drop ALL,
# no-new-privileges, 2g/2g, tmpfs /tmp, --rm. No /run/secrets, no key (not even a fake), no OpenClaw config; node -e only,
# with every proxy env empty and hard timeouts.
#  3a dns.lookup api.anthropic.com: recorded (resolving alone is not a FAIL)
#  3b https.get https://api.anthropic.com/v1/models, no proxy, no auth: PASS only on a network error; any HTTP status FAILs
#  3c TCP 1.1.1.1:443, 8.8.8.8:443, [2606:4700:4700::1111]:443: PASS only on error or timeout
#  3d positive control: TCP connect to oc551-edge:3128, closed without sending a byte (must connect)
#  4  CONNECT oc551-p95-allowlist-test.invalid:443 through oc551-edge:3128: 403, and exactly 1 new refused edge line
# Guards: refuses if oc551-p95 exists or the image is not the reviewed digest; oc551-int must be Internal=true; the IDs and
# StartedAt of the two real containers are recorded before and must be unchanged (and Running) after. On the real
# containers this script only runs `inspect -f` and reads the edge's logs (see --selftest). Output: counts and codes only.
# Usage: openclaw/p95-sidecar.sh <reviewed worker digest prefix>   |   openclaw/p95-sidecar.sh --selftest
# (receipt: ~/audit/tsenta-openclaw-1013/P95-SIDECAR-<time>.txt; exit 0 PASS, 1 FAIL, 2 refused)
set -uo pipefail
D=(docker --context desktop-linux)
REAL="oc551-worker oc551-edge"
if [ "${1:-}" = --selftest ]; then   # no docker verb but inspect -f and logs may name a real container on the same line
  V='(^|[^a-z-])(exec|stop|rm|kill|cp|restart|pause|update|attach|commit|export)([^a-z]|$)'
  n=$(grep -vE '^\s*#' "$0" | grep -E "$V" | grep -cE 'oc551-(worker|edge)([^:a-z-]|$)'); true
  [ "$n" = 0 ] && { echo "selftest PASS (no forbidden verb next to a real container name)"; exit 0; }
  echo "selftest FAIL ($n lines)"; grep -vE '^\s*#' "$0" | grep -E "$V" | grep -nE 'oc551-(worker|edge)([^:a-z-]|$)'; exit 1
fi
W_EXPECT="${1:?reviewed worker digest prefix}"
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/P95-SIDECAR-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
state() { for c in $REAL; do "${D[@]}" inspect -f '{{.Name}} {{.Id}} {{.State.StartedAt}} {{.State.Running}}' "$c" 2>/dev/null || echo "$c missing"; done; }
edgecount() {  # $1 python expression over o (one parsed edge log line); prints the count, or "unreadable"
  local l; l=$("${D[@]}" logs oc551-edge 2>&1) || { echo unreadable; return; }
  printf '%s\n' "$l" | python3 -I -c '
import json, sys
n = 0
for line in sys.stdin:
    try: o = json.loads(line)
    except ValueError: continue
    if isinstance(o, dict) and ('"$1"'): n += 1
print(n)'
}
P95='o.get("op") == "CONNECT" and o.get("target") == "oc551-p95-allowlist-test.invalid:443" and o.get("verdict") == "refused"'
API='o.get("op") == "CONNECT" and o.get("target") == "api.anthropic.com:443"'
ALL='True'

img=$("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3) || { echo "refusing: worker image not found" >&2; exit 2; }
case "${img#sha256:}" in "$W_EXPECT"*) ;; *) echo "refusing: worker image ${img:7:12} is not the reviewed $W_EXPECT" >&2; exit 2 ;; esac
"${D[@]}" inspect oc551-p95 >/dev/null 2>&1 && { echo "refusing: oc551-p95 already exists" >&2; exit 2; }
[ "$("${D[@]}" ps -aq --filter label=oc551p95=1 | wc -l | tr -d ' ')" = 0 ] || { echo "refusing: an oc551p95=1 container exists" >&2; exit 2; }
trap '[ "$("${D[@]}" inspect -f "{{index .Config.Labels \"oc551p95\"}}" oc551-p95 2>/dev/null)" = 1 ] && "${D[@]}" rm -f oc551-p95 >/dev/null 2>&1' EXIT

say "9.5 steps 3+4 keyless sidecar $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$(dirname "$0")/.." rev-parse --short HEAD); image ${img:7:12}"
BEFORE=$(state)
check "real containers present and running before" "$(printf '%s\n' "$BEFORE" | awk '$4 == "true"' | wc -l | tr -d ' ')" 2
check "oc551-int Internal" "$("${D[@]}" network inspect -f '{{.Internal}}' oc551-int 2>/dev/null)" true
e_p95=$(edgecount "$P95"); e_api=$(edgecount "$API"); e_all=$(edgecount "$ALL")
info "edge lines before (all / p95 refused / api.anthropic.com)" "$e_all / $e_p95 / $e_api"
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (preconditions)"; exit 1; }

JS='
const dns = require("dns"), https = require("https"), net = require("net");
setTimeout(() => { console.log("overall timeout"); process.exit(3); }, 45000).unref();
const out = (k, v) => console.log(k + " " + v);
const tcp = (host, port, ms) => new Promise(r => { const s = net.connect({ host, port }); let d = false;
  const end = v => { if (!d) { d = true; s.destroy(); r(v); } };
  s.setTimeout(ms, () => end("timeout")); s.on("connect", () => end("connected")); s.on("error", e => end("error:" + (e.code || "x"))); });
(async () => {
  out("3a", await new Promise(r => { const t = setTimeout(() => r("timeout"), 5000);
    dns.lookup("api.anthropic.com", { all: true }, (e, a) => { clearTimeout(t); r(e ? "error:" + (e.code || "x") : "resolved:" + a.length); }); }));
  out("3b", await new Promise(r => { let d = false; const end = v => { if (!d) { d = true; r(v); } };
    const q = https.get("https://api.anthropic.com/v1/models", { timeout: 8000, agent: false }, res => { end("status:" + res.statusCode); res.destroy(); });
    q.on("timeout", () => { q.destroy(); end("timeout"); }); q.on("error", e => end("error:" + (e.code || "x"))); }));
  for (const [h, p] of [["1.1.1.1", 443], ["8.8.8.8", 443], ["2606:4700:4700::1111", 443]]) out("3c " + h, await tcp(h, p, 5000));
  out("3d", await tcp("oc551-edge", 3128, 5000));
  out("4", await new Promise(r => { const s = net.connect({ host: "oc551-edge", port: 3128 }); let b = "", d = false;
    const end = v => { if (!d) { d = true; s.destroy(); r(v); } };
    s.setTimeout(8000, () => end("timeout"));
    s.on("connect", () => s.write("CONNECT oc551-p95-allowlist-test.invalid:443 HTTP/1.1\r\nHost: oc551-p95-allowlist-test.invalid:443\r\n\r\n"));
    s.on("data", c => { b += c; const i = b.indexOf("\r\n"); if (i >= 0) end("status:" + (b.slice(0, i).split(" ")[1] || "x")); });
    s.on("error", e => end("error:" + (e.code || "x"))); s.on("close", () => end("closed")); }));
})();'
res=$("${D[@]}" run --rm --name oc551-p95 --label oc551p95=1 --network oc551-int --read-only --cap-drop ALL \
  --security-opt no-new-privileges --memory 2g --memory-swap 2g --tmpfs /tmp --user node --entrypoint node \
  -e HTTP_PROXY= -e HTTPS_PROXY= -e http_proxy= -e https_proxy= -e ALL_PROXY= -e NO_PROXY= -e NODE_USE_ENV_PROXY= \
  "$img" -e "$JS" 2>&1); rrc=$?
check "sidecar exit" "$rrc" 0
v() { printf '%s\n' "$res" | sed -n "s/^$1 //p" | head -1; }
r3a=$(v 3a); info "3a dns.lookup api.anthropic.com (recorded, not a FAIL)" "${r3a:-none}"
r3b=$(v 3b); case "$r3b" in error:*|timeout) check "3b direct https to api.anthropic.com is a network error" yes yes; info "3b result" "$r3b" ;;
  *) check "3b direct https to api.anthropic.com is a network error" "no ($r3b)" yes ;; esac
for h in 1.1.1.1 8.8.8.8 2606:4700:4700::1111; do r=$(v "3c $h")
  case "$r" in error:*|timeout) check "3c direct TCP $h:443 fails" yes yes; info "3c $h" "$r" ;; *) check "3c direct TCP $h:443 fails" "no (${r:-none})" yes ;; esac
done
check "3d positive control: TCP to oc551-edge:3128" "$(v 3d)" connected
check "4 CONNECT to a non-allowlisted host through the edge" "$(v 4)" status:403
sleep 1
a_p95=$(edgecount "$P95"); a_api=$(edgecount "$API"); a_all=$(edgecount "$ALL")
check "4 new refused edge lines for oc551-p95-allowlist-test.invalid:443" "$([ "$a_p95" != unreadable ] && [ "$e_p95" != unreadable ] && echo $((a_p95 - e_p95)) || echo unreadable)" 1
check "edge CONNECTs to api.anthropic.com:443 (still no turn)" "$a_api" 0
info "edge lines added during the run (all)" "$([ "$a_all" != unreadable ] && [ "$e_all" != unreadable ] && echo $((a_all - e_all)) || echo unreadable)"

AFTER=$(state)
check "real containers unchanged (Id, StartedAt) and running" "$([ "$BEFORE" = "$AFTER" ] && printf '%s\n' "$AFTER" | awk '$4 != "true"{x=1} END{print x ? "no" : "yes"}' || echo changed)" yes
check "oc551-p95 left" "$("${D[@]}" ps -aq --filter label=oc551p95=1 | wc -l | tr -d ' ')" 0
say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
