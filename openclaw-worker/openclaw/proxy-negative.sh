#!/bin/bash
# 551 contract 9.5 steps 3 and 4 with a FAKE key (551 v23 split; step 2, the routed real call, stays HELD). FAKE ONLY.
# The fill uses the real route (fill-route.py opened by the offscreen fill-browser), whose page generates a fake
# "sk-ant-canary-" value. This script never learns it. The edge runs with EDGE_ALLOW empty, so nothing can leave.
# Step 3, negative proof: copy the main config to a temporary test dir in the worker's /demo/state tmpfs, remove
#   proxy.proxyUrl from the copy only, unset every proxy env, give the test its own state dir and HOME, and run the
#   contract's ping (`openclaw agent --agent main --message-file <file> --json --timeout 120`). The key reaches the test
#   process by export inside the container shell, never argv. PASS only on a network-level error (EAI_AGAIN, ENOTFOUND,
#   ENETUNREACH, ECONNREFUSED, ETIMEDOUT or a timeout). Any provider answer (an HTTP status or an API error body) or a
#   success means a route out exists: FAIL. A failure before any model call (e.g. "No callable tools remain", seen by 551
#   at 20:39) proves nothing: INCONCLUSIVE. A new CONNECT at the edge during step 3 means the copy still routed through the
#   proxy: FAIL. Then the test dir is deleted and the main config's sha256 must equal the value recorded at start.
# Step 4, allowlist: from inside the worker, a CONNECT through the edge to a non-allowlisted host gets 403, and the edge
#   logs exactly that target as refused.
# Output is never printed raw: the test's output is classified inside the container; only the class, the matched error
# code, a count of key-shaped tokens and up to 5 pattern-redacted tail lines reach the receipt.
# Usage: openclaw/proxy-negative.sh   (receipt: ~/audit/tsenta-openclaw-1013/PROXY-NEGATIVE-<time>.txt)
# Exit 0 PASS, 1 FAIL, 3 INCONCLUSIVE.
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
BROWSER="${FILL_BROWSER:-$AUD/bin/fill-browser}"
OUT="$AUD/PROXY-NEGATIVE-$(date +%Y%m%dT%H%M%S).txt"
FAILS=0; INCONCLUSIVE=0; ROUTE_PID=""
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
wexec() { "${D[@]}" exec -u node oc551-worker "$@"; }
labelled() { [ "$("${D[@]}" inspect -f '{{index .Config.Labels "oc551"}}' "$1" 2>/dev/null)" = 1 ]; }
lcount() { local c="$1" l; shift; l=$("${D[@]}" logs "$c" 2>&1) || { echo unreadable; return; }; printf '%s\n' "$l" | grep -c "$@"; true; }   # 551 RC-1: a failed docker logs is "unreadable", never a 0
edge_connects() { lcount oc551-edge '"op":"CONNECT"'; }
delta() { case "$1$2" in *[!0-9]*) echo unreadable ;; *) echo $(($2 - $1)) ;; esac; }
cleanup() {
  [ -n "$ROUTE_PID" ] && kill "$ROUTE_PID" 2>/dev/null
  for c in oc551-worker oc551-edge; do labelled "$c" && "${D[@]}" rm -f "$c" >/dev/null 2>&1; done
}
trap cleanup EXIT
trap 'exit 130' INT TERM

say "9.5 steps 3+4 (FAKE) $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$HERE/.." rev-parse --short HEAD); worker image $("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3 | cut -c8-19); edge image $("${D[@]}" image inspect -f '{{.Id}}' oc551-edge:1 | cut -c8-19)"
# 551 PN-1: hard guard. Step 3 reads model_key into the test env, which is safe only because this script made the fill
# itself with a FAKE value. It must never touch a worker that might hold a REAL key, so any oc551 container ends it here.
n=$("${D[@]}" ps -aq --filter label=oc551=1 | wc -l | tr -d ' ')
[ "$n" = 0 ] || { say "REFUSING: $n oc551 container(s) exist; this FAKE-only test never runs beside another worker"; trap - EXIT; exit 1; }
check "precondition: browser tool built" "$([ -x "$BROWSER" ] && echo yes)" yes
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (preconditions)"; exit 1; }

"$HERE/phase1.sh" net >/dev/null
eo=$(EDGE_ALLOW="" "$HERE/phase1.sh" edge 2>&1) || { say "FAIL  edge start:"; printf '%s\n' "$eo" | sed 's/^/        /' | tee -a "$OUT"; exit 1; }
check "edge allowlist is empty" "$(lcount oc551-edge -F '"allow":[]')" 1
wo=$(CANARY="" "$HERE/phase1.sh" worker 2>&1) || { say "FAIL  worker start:"; printf '%s\n' "$wo" | sed 's/^/        /' | tee -a "$OUT"; exit 1; }

# the fake fill through the real route (the page makes the value; this script never sees it)
fd=$(mktemp -d); mkfifo -m 600 "$fd/url"
FILL_TIMEOUT=60 python3 -I "$HERE/fill-route.py" oc551-worker > "$fd/url" & ROUTE_PID=$!
exec 3< "$fd/url"; read -r line <&3; url="${line##* }"; rm -f "$fd/url"; rmdir "$fd"
r=$("$BROWSER" "$url" 2>/dev/null | paste -sd' ' -)
wait "$ROUTE_PID" 2>/dev/null; ROUTE_PID=""; exec 3<&-
check "fake fill via the browser route" "$r" "filled: yes dom-inputs: 0"
[ "$r" = "filled: yes dom-inputs: 0" ] || { say "RESULT: FAIL (no fake fill of our own; step 3 never reads a key it did not fill)"; exit 1; }
for _ in $(seq 1 150); do "${D[@]}" logs oc551-worker 2>&1 | grep -qE '\[gateway\] ready$' && break; sleep 0.2; done
check "'[gateway] ready' log lines" "$(lcount oc551-worker -E '\[gateway\] ready$')" 1
main_sha=$(wexec cat /demo/state/config.sha256)
check "main config sha256 at start matches the entrypoint's record" "$(wexec sha256sum /demo/state/openclaw.json5 | cut -c1-64)" "$main_sha"
sleep 5   # let the post-start prewarm attempt land before the step 3 baseline

say "== step 3: no-proxy negative proof (temporary test config only)"
before=$(edge_connects)
res=$(wexec sh -c '
  set -u; umask 077
  T=$(mktemp -d /demo/state/t95.XXXXXX); mkdir -p "$T/state" "$T/home"
  # 551 PN-2 (option a): the TEST COPY also turns tsenta off and drops tools.alsoAllow, so the run reaches the model call
  M=/demo/state/openclaw.json5
  grep -v "^  proxy: { proxyUrl: \"http://oc551-edge:3128\" },\$" "$M" | grep -v "^    alsoAllow: \[\"tsenta__\*\"\],\$" \
    | sed "s/^      tsenta: { url:/      tsenta: { enabled: false, url:/" > "$T/openclaw.json5"
  echo "copy-proxyUrl-lines $(grep -c proxyUrl "$T/openclaw.json5")"
  diff "$M" "$T/openclaw.json5" > "$T/diff"
  echo "diff-removed $(grep -c "^<" "$T/diff") proxy $(grep "^<" "$T/diff" | grep -c proxyUrl) alsoAllow $(grep "^<" "$T/diff" | grep -c alsoAllow) tsenta $(grep "^<" "$T/diff" | grep -c "tsenta: { url:")"
  echo "diff-added $(grep -c "^>" "$T/diff") enabled-false $(grep "^>" "$T/diff" | grep -c "tsenta: { enabled: false, url:")"
  printf "Reply with the single word pong.\n" > "$T/ping.md"
  (
    unset HTTPS_PROXY HTTP_PROXY ALL_PROXY https_proxy http_proxy all_proxy NO_PROXY no_proxy
    OPENCLAW_CONFIG_PATH="$T/openclaw.json5"; OPENCLAW_STATE_DIR="$T/state"; HOME="$T/home"
    ANTHROPIC_API_KEY="$(cat /run/secrets/model_key)"
    export OPENCLAW_CONFIG_PATH OPENCLAW_STATE_DIR HOME ANTHROPIC_API_KEY
    exec timeout 150 openclaw agent --agent main --message-file "$T/ping.md" --json --timeout 120
  ) > "$T/out" 2>&1
  echo "rc $?"
  E="EAI_AGAIN|ENOTFOUND|ENETUNREACH|ECONNREFUSED|ETIMEDOUT|ECONNRESET"
  net=$(grep -E "$E" "$T/out" | grep -F "api.anthropic.com" | grep -oE "$E" | head -1)   # 551 PN-3: must name the model host
  netany=$(grep -oE "$E" "$T/out" | head -1)
  api=$(grep -ciE "authentication_error|invalid x-api-key|invalid_api_key|\"type\": *\"error\"|\"status\": *[45][0-9][0-9]|status code [45][0-9][0-9]|HTTP/[0-9.]+ [45][0-9][0-9]" "$T/out")
  pre=$(grep -c "No callable tools remain" "$T/out")
  echo "net ${net:-none}"; echo "netany ${netany:-none}"; echo "api $api"; echo "pre $pre"
  echo "keyshaped $(grep -c "sk-ant-" "$T/out")"
  tail -5 "$T/out" | sed -E "s/sk-ant-[A-Za-z0-9_-]+/<REDACTED-KEY>/g; s/token=[^ &\"]+/token=<REDACTED>/g; s/^/tail| /"
  rm -rf "$T"; echo "testdir-left $(ls -d /demo/state/t95.* 2>/dev/null | wc -l)"
')
after=$(edge_connects)
v() { printf '%s\n' "$res" | sed -n "s/^$1 //p" | head -1; }
check "step 3: proxyUrl lines left in the test copy" "$(v copy-proxyUrl-lines)" 0
check "step 3: test copy vs main, removed lines by kind" "$(v diff-removed)" "3 proxy 1 alsoAllow 1 tsenta 1"
check "step 3: test copy vs main, added lines by kind" "$(v diff-added)" "1 enabled-false 1"
info "step 3: ping exit code (124 = timeout)" "$(v rc)"
check "step 3: key-shaped tokens in the test output" "$(v keyshaped)" 0
printf '%s\n' "$res" | sed -n 's/^tail| /        /p' | tee -a "$OUT"
check "step 3: new CONNECTs at the edge during the test (the copy must not use the proxy)" "$(delta "$before" "$after")" 0
if [ "$(v api)" != 0 ] || [ "$(v rc)" = 0 ]; then say "FAIL  step 3: a provider answered or the call succeeded (route out exists)"; FAILS=$((FAILS + 1))
elif [ "$(v net)" != none ]; then say "ok    step 3: network-level failure naming api.anthropic.com = $(v net) (rc $(v rc))"
elif [ "$(v pre)" != 0 ]; then say "INCONCLUSIVE  step 3: failed before any model call (No callable tools remain); nothing proven"; INCONCLUSIVE=1
elif [ "$(v netany)" != none ]; then say "INCONCLUSIVE  step 3: network error $(v netany) does not name api.anthropic.com; nothing proven"; INCONCLUSIVE=1
elif [ "$(v rc)" = 124 ]; then say "INCONCLUSIVE  step 3: timed out with no error naming api.anthropic.com; nothing proven"; INCONCLUSIVE=1
else say "INCONCLUSIVE  step 3: failure not classified (see the redacted tail); nothing proven"; INCONCLUSIVE=1; fi
check "step 3: test dirs left" "$(v testdir-left)" 0
check "step 3: main config sha256 unchanged" "$(wexec sha256sum /demo/state/openclaw.json5 | cut -c1-64)" "$main_sha"

say "== step 4: CONNECT to a non-allowlisted host through the edge"
before=$(edge_connects)
code=$(wexec node -e '
  const r = require("http").request({ host: "oc551-edge", port: 3128, method: "CONNECT", path: "example.com:443", timeout: 5000 });
  r.on("connect", (res, s) => { console.log(res.statusCode); s.destroy(); });
  r.on("response", (res) => console.log(res.statusCode));
  r.on("timeout", () => { console.log("timeout"); r.destroy(); });
  r.on("error", (e) => console.log("error " + e.code));
  r.end();')
check "step 4: proxy answer to CONNECT example.com:443" "$code" 403
sleep 0.5
check "step 4: new edge CONNECT lines" "$(delta "$before" "$(edge_connects)")" 1
if el=$("${D[@]}" logs oc551-edge 2>&1); then
  check "step 4: edge logged example.com:443 refused" "$(printf '%s\n' "$el" | grep '"op":"CONNECT"' | grep -F '"target":"example.com:443"' | grep -cF '"verdict":"refused"')" 1
  info "edge CONNECTs over the whole run (host:port/verdict)" "$(printf '%s\n' "$el" | grep '"op":"CONNECT"' | grep -oE '"target":"[^"]*","verdict":"[^"]*"' | sort | uniq -c | paste -sd' ' -)"
else say "FAIL  docker logs edge failed"; FAILS=$((FAILS + 1)); fi

if [ "$FAILS" -gt 0 ]; then say "RESULT: FAIL ($FAILS checks)"; rc=1
elif [ "$INCONCLUSIVE" -gt 0 ]; then say "RESULT: INCONCLUSIVE (step 3 proved nothing)"; rc=3
else say "RESULT: PASS"; rc=0; fi
say "receipt: $OUT"
exit "$rc"
