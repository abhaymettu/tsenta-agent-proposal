#!/bin/bash
# Stage the REAL key fill. Run ONLY on the operator's GO, with the user at the Mac.
# Source (551 v25 RF-3; read by the operator by direct SQL at 20:40:28): user message 01M4W10Q007H0YZ6A68VMF55RV at
#   20:39:18, exact: "We do not need to be so safe about the demo key. Just fill it in however you can. Normally it is fine".
#   Context: a manual Incognito fill had been asked about at 20:38:55. A normal one-use page is INTERPRETED as allowed by
#   this; it was not dictated, and the user did not say "normal Chrome". Parent 20:39:26: the simplest supported route; no
#   disk, git, log or chat; worker, proxy and tool checks kept. Incognito is a SHOULD (551 U2).
# 1. Refuses unless no oc551 container exists and both image IDs equal the reviewed digests given as arguments.
# 2. Starts the edge with the real allowlist (exactly api.anthropic.com:443) and the worker (gateway mode), both through
#    phase1.sh with their tmpfs and swap gates.
# 3. Starts fill-route.py and prints its single-use URL. The user opens it, pastes the key into the blank password field
#    and presses Fill. The value goes browser -> loopback route -> fill-key.sh stdin -> docker exec stdin -> the worker's
#    0600 tmpfs file. This script never sees it, and nothing about it is written.
# 4. If the route closes without a fill (timeout, refusal, Ctrl-C), stops both containers, confirms 0 left, exits 1 (551
#    RF-1). Presence is tested with `test -s` inside the worker; no size is ever printed. Until the fill succeeds, an
#    EXIT/INT/TERM trap removes both containers.
# 5. After a fill, waits for '[gateway] ready', runs openclaw/real-checks.sh (metadata only), and prints the stop command.
# No agent turn, no model call is made here. The 9.5 routed call and G-h come after, each on its own GO.
# Usage: openclaw/real-fill.sh <reviewed worker digest prefix> <reviewed edge digest prefix>   (env FILL_TIMEOUT, default 900)
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
W_EXPECT="${1:?reviewed worker digest prefix}"; E_EXPECT="${2:?reviewed edge digest prefix}"
w=$("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3 | cut -c8-); e=$("${D[@]}" image inspect -f '{{.Id}}' oc551-edge:1 | cut -c8-)
case "$w" in "$W_EXPECT"*) ;; *) echo "refusing: worker image ${w:0:12} is not the reviewed $W_EXPECT" >&2; exit 2 ;; esac
case "$e" in "$E_EXPECT"*) ;; *) echo "refusing: edge image ${e:0:12} is not the reviewed $E_EXPECT" >&2; exit 2 ;; esac
[ "$("${D[@]}" ps -aq --filter label=oc551=1 | wc -l | tr -d ' ')" = 0 ] || { echo "refusing: oc551 containers already exist" >&2; exit 2; }
[ -z "${EDGE_ALLOW+x}" ] || { echo "refusing: EDGE_ALLOW is set; the real run uses phase1.sh's default (api.anthropic.com:443)" >&2; exit 2; }

FILLED=0; ROUTE_PID=""
labelled() { [ "$("${D[@]}" inspect -f '{{index .Config.Labels "oc551"}}' "$1" 2>/dev/null)" = 1 ]; }
teardown() {
  [ -n "$ROUTE_PID" ] && kill "$ROUTE_PID" 2>/dev/null
  for c in oc551-worker oc551-edge; do labelled "$c" && "${D[@]}" rm -f "$c" >/dev/null 2>&1; done
  echo "stopped; oc551 containers left: $("${D[@]}" ps -aq --filter label=oc551=1 | wc -l | tr -d ' ')"
}
trap '[ "$FILLED" = 1 ] || teardown' EXIT
trap 'exit 130' INT TERM

"$HERE/phase1.sh" net >/dev/null || exit 1
"$HERE/phase1.sh" edge >/dev/null || { echo "edge start failed" >&2; exit 1; }
CANARY="" "$HERE/phase1.sh" worker >/dev/null || { echo "worker start failed" >&2; exit 1; }
echo "edge and worker up (worker ${w:0:12}, edge ${e:0:12}); worker waiting for the fill"

FILL_TIMEOUT="${FILL_TIMEOUT:-900}" python3 -I "$HERE/fill-route.py" oc551-worker & ROUTE_PID=$!   # prints the URL line
wait "$ROUTE_PID"; echo "route closed (exit $?)"; ROUTE_PID=""
if ! "${D[@]}" exec -u node oc551-worker test -s /run/secrets/model_key 2>/dev/null; then
  echo "no fill arrived; stopping both containers"; exit 1   # the EXIT trap tears down
fi
FILLED=1; echo "filled: yes (presence only)"

for _ in $(seq 1 300); do "${D[@]}" logs oc551-worker 2>&1 | grep -qE '\[gateway\] ready$' && break; sleep 0.2; done
"$HERE/real-checks.sh"; rc=$?
echo "To stop: docker --context desktop-linux stop oc551-worker oc551-edge"
echo "Both run with --rm and keep the key only in tmpfs, so stopping deletes the key with the container."
exit "$rc"
