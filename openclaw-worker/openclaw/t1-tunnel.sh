#!/bin/bash
# T-1 (551 v43 A1-e): keyless proof that the Gateway's MCP path works through the edge, before any model call. A sidecar
# (oc551-t1, label oc551p95=1, NOT oc551=1) on the LIVE oc551-int runs the reviewed worker image by digest: read-only,
# cap-drop ALL, no-new-privileges, 2g/2g, tmpfs /tmp, --rm; no /run/secrets, no key, no OpenClaw config; node -e only.
#  1 CONNECT oc551-edge:8560 through oc551-edge:3128: 200 Connection Established (what the Gateway's proxied fetch does)
#  2 inside that tunnel, POST /mcp initialize (with Content-Length): HTTP 200 and result.serverInfo.name tsenta-sandbox
# Edge deltas: CONNECT oc551-edge:8560 allowed +1, tool forwarded 200 +1, api.anthropic.com:443 0; core events delta 0
# (initialize is not a tool call). The real containers are only inspected and the edge's log read; their Id and StartedAt
# must be unchanged. Run only on the operator's GO, after edge-restart.sh and the core-only restart.
# Usage: openclaw/t1-tunnel.sh <reviewed worker digest prefix>   (exit 0 PASS, 1 FAIL, 2 refused)
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
W_EXPECT="${1:?reviewed worker digest prefix}"
[[ $W_EXPECT =~ ^[0-9a-f]{16,}$ ]] || { echo "refusing: digest prefix must be at least 16 hex characters" >&2; exit 2; }   # 551 v44 D-1
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/T1-TUNNEL-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
state() { "${D[@]}" inspect -f '{{.Name}} {{.Id}} {{.State.StartedAt}} {{.State.Running}}' oc551-worker oc551-edge 2>/dev/null || echo missing; }
edge() {  # t8_allowed tool_200 api_any   (or "unreadable")
  local l; l=$("${D[@]}" logs oc551-edge 2>&1) || { echo unreadable; return; }
  printf '%s\n' "$l" | python3 -I -c '
import json, sys
a = g = n = 0
for line in sys.stdin:
    try: x = json.loads(line)
    except ValueError: continue
    if not isinstance(x, dict): continue
    if x.get("op") == "CONNECT" and x.get("target") == "oc551-edge:8560" and x.get("verdict") == "allowed": a += 1
    if x.get("op") == "CONNECT" and x.get("target") == "api.anthropic.com:443": n += 1
    if x.get("op") == "tool" and x.get("verdict") == "forwarded" and x.get("status") == 200: g += 1
print(a, g, n)'
}
events() { python3 -I -c 'import sqlite3, sys; c = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True); print(c.execute("SELECT count(*) FROM events").fetchone()[0])' "$HERE/../run/core.db" 2>/dev/null || echo unreadable; }

img=$("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3) || { echo "refusing: worker image not found" >&2; exit 2; }
case "${img#sha256:}" in "$W_EXPECT"*) ;; *) echo "refusing: worker image ${img:7:12} is not the reviewed $W_EXPECT" >&2; exit 2 ;; esac
"${D[@]}" inspect oc551-t1 >/dev/null 2>&1 && { echo "refusing: oc551-t1 already exists" >&2; exit 2; }
[ "$("${D[@]}" ps -aq --filter label=oc551p95=1 | wc -l | tr -d ' ')" = 0 ] || { echo "refusing: an oc551p95=1 container exists" >&2; exit 2; }
trap '[ "$("${D[@]}" inspect -f "{{index .Config.Labels \"oc551p95\"}}" oc551-t1 2>/dev/null)" = 1 ] && "${D[@]}" rm -f oc551-t1 >/dev/null 2>&1' EXIT

say "T-1 keyless tunnel proof $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$HERE/.." rev-parse --short HEAD); image ${img:7:12}"
BEFORE=$(state)
check "real containers running before" "$(printf '%s\n' "$BEFORE" | awk '$4 == "true"' | wc -l | tr -d ' ')" 2
check "edge mcp_token present (test -s, 600 node)" "$("${D[@]}" exec -u node oc551-edge sh -c 'test -s /run/secrets/mcp_token && stat -c "%a %U" /run/secrets/mcp_token' 2>/dev/null)" "600 node"
read -r a0 g0 n0 <<< "$(edge)"; ev0=$(events)
check "edge log readable before" "$([[ $a0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes
check "core events readable before" "$([[ $ev0 =~ ^[0-9]+$ ]] && echo yes || echo no)" yes
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (preconditions)"; exit 1; }

JS='
const net = require("net");
setTimeout(() => { console.log("overall timeout"); process.exit(3); }, 20000).unref();
const s = net.connect({ host: "oc551-edge", port: 3128 }); let buf = "", stage = 0;
s.setTimeout(10000, () => { console.log("timeout stage " + stage); s.destroy(); });
s.on("connect", () => s.write("CONNECT oc551-edge:8560 HTTP/1.1\r\nHost: oc551-edge:8560\r\n\r\n"));
s.on("data", c => { buf += c;
  if (stage === 0) { const i = buf.indexOf("\r\n\r\n"); if (i < 0) return;
    const st = buf.split("\r\n")[0].split(" ")[1] || "x"; console.log("1 status:" + st); buf = buf.slice(i + 4);
    if (st !== "200") { s.destroy(); return; }
    stage = 1;
    const body = JSON.stringify({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "t1", version: "1" } } });
    s.write("POST /mcp HTTP/1.1\r\nHost: oc551-edge:8560\r\nContent-Type: application/json\r\nAccept: application/json, text/event-stream\r\nContent-Length: " + Buffer.byteLength(body) + "\r\nConnection: close\r\n\r\n" + body); } });
s.on("end", () => { if (stage !== 1) return; const head = buf.split("\r\n\r\n")[0], body = buf.slice(head.length + 4);
  console.log("2 status:" + (head.split("\r\n")[0].split(" ")[1] || "x"));
  try { const j = JSON.parse(body.slice(body.indexOf("{"), body.lastIndexOf("}") + 1)); console.log("2 server:" + ((j.result || {}).serverInfo || {}).name); } catch (e) { console.log("2 server:unparseable"); } });
s.on("error", e => console.log("error:" + (e.code || "x")));'
res=$("${D[@]}" run --rm --name oc551-t1 --label oc551p95=1 --network oc551-int --read-only --cap-drop ALL \
  --security-opt no-new-privileges --memory 2g --memory-swap 2g --tmpfs /tmp --user node --entrypoint node \
  -e HTTP_PROXY= -e HTTPS_PROXY= -e http_proxy= -e https_proxy= -e ALL_PROXY= -e NO_PROXY= -e NODE_USE_ENV_PROXY= \
  "$img" -e "$JS" 2>&1); rrc=$?
check "sidecar exit" "$rrc" 0
v() { printf '%s\n' "$res" | sed -n "s/^$1 //p" | head -1; }
check "1 CONNECT oc551-edge:8560 through the proxy" "$(v 1)" status:200
check "2 POST /mcp initialize inside the tunnel" "$(v 2 | grep '^status' | head -1)" status:200
check "2 serverInfo name" "$(printf '%s\n' "$res" | sed -n 's/^2 server://p' | head -1)" tsenta-sandbox
sleep 1
read -r a1 g1 n1 <<< "$(edge)"; ev1=$(events)
if [[ $a1 =~ ^[0-9]+$ ]]; then
  check "edge CONNECT oc551-edge:8560 allowed delta" "$(( a1 - a0 ))" 1
  check "edge tool forwarded 200 delta" "$(( g1 - g0 ))" 1
  check "edge CONNECTs to api.anthropic.com:443 (cumulative)" "$n1" 0
else check "edge log readable after" no yes; fi
check "core events delta (initialize is not a tool call)" "$([[ $ev1 =~ ^[0-9]+$ ]] && echo $(( ev1 - ev0 )) || echo unreadable)" 0
check "real containers unchanged (Id, StartedAt) and running" "$([ "$BEFORE" = "$(state)" ] && echo yes || echo changed)" yes
check "oc551-t1 left" "$("${D[@]}" ps -aq --filter label=oc551p95=1 | wc -l | tr -d ' ')" 0
say "RESULT: $([ "$FAILS" -eq 0 ] && echo PASS || echo "FAIL ($FAILS checks)")"
say "receipt: $OUT"
[ "$FAILS" -eq 0 ]
