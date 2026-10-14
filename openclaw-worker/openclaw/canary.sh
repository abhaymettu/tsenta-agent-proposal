#!/bin/bash
# Memory-only key route proof with FAKE keys (551 s9.4 steps a-e, C5-C7, CA1-CA7; operator 19:23). No real
# credential is involved, and no model request is possible: the worker's only network is oc551-int (--internal). Its
# only peer, in stage 2b, is an edge started with EDGE_ALLOW empty, which refuses every CONNECT.
# Every fill goes through the real route: fill-route.py, opened by the offscreen WebKit tool (fill-browser), which
# generates the canary inside the page ("sk-ant-canary-" + 48 hex) and submits it with the page's own script, so the
# POST carries a real browser Origin under the page's CSP. This script learns the canary only by reading it back from
# the container's tmpfs (the positive control). It reaches grep only through a file descriptor, never argv, and is never
# printed or written. The host ps sampler matches the fixed prefix, so it needs no advance knowledge of the value.
# An EXIT/INT/TERM trap removes the route, the sampler, the worker and the edge, and clears the canary. A failed check
# does not abort the run; only a container that cannot start ends a phase.
# Not covered (551 v2, an owner or parent decision): VM transit (dockerd, containerd and the shim relay exec stdin
# outside the container cgroup) and host transit (macOS swap, which is encrypted).
# Reading the value back from the tmpfs is for FAKE canaries only. Never run this, or anything like it, against a real
# key: the real fill (fill-route.py) has no read-back. The script refuses to start if a model_key already exists.
# Host scans report coverage: a location is "clean" only if every file under it was read; unreadable paths are counted
# and listed as UNVERIFIED, never counted as clean. A container command that fails is a FAIL, never a 0.
# Usage: openclaw/canary.sh   (receipt: ~/audit/tsenta-openclaw-1013/CANARY-RECEIPT-<time>.txt)
# Exit 0 = PASS (every check ok, every scanned root fully read); 2 = PASS-UNVERIFIED (checks ok, but N roots had unreadable
# paths, listed for acceptance or rejection); 1 = FAIL.
set -uo pipefail
D=(docker --context desktop-linux)
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(dirname "$HERE")"
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
DDLOG="$HOME/Library/Containers/com.docker.docker/Data/log"
BROWSER="${FILL_BROWSER:-$AUD/bin/fill-browser}"
OUT="$AUD/CANARY-RECEIPT-$(date +%Y%m%dT%H%M%S).txt"
PREFIX="sk-ant-canary-"
CAN=""
FAILS=0
INCOMPLETE=0   # roots with unreadable paths: their zeros are UNVERIFIED, so the run cannot be a plain PASS (551 G1)
ROUTE_PID=""; PS_PID=""; NPM_PID=""; LOG_PID=""; WAIT_PID=""
FLAG="$(mktemp -u "$AUD/.sampling.XXXXXX")"

say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
count() { grep -caF -f <(printf '%s\n' "$CAN") || true; }                                # stdin: lines with the canary
cscan() {  # $1 label, then a command; FAIL if the command fails, else the canary count must be 0 (or $EXPECT)
  local label="$1"; shift; local res
  res=$( { "$@" 2>/dev/null | count; echo " ${PIPESTATUS[0]}"; } | tr -s ' \n' ' ' )
  set -- $res
  if [ "${2:-x}" != 0 ]; then say "FAIL  $label: command failed (exit ${2:-?}), nothing proven"; FAILS=$((FAILS + 1))
  else check "$label" "$1" "${EXPECT:-0}"; fi
}
SCAN_TMP="$(mktemp -d "$AUD/.scan.XXXXXX")"   # holds the stamp and fill outputs, never the canary
STAMP="$SCAN_TMP/stamp"; : > "$STAMP"          # made before any canary exists; --recent roots read files changed after it
hscan() {  # $1 label, $2 path, $3 full|recent: openclaw/scan-host.py (regular files only, never blocks or follows; 551 v10/v11)
  local label="$1" p="$2" mode="${3:-full}" line rc real hits nh fr br old sl fi so dv de ov ch to va sample
  [ -e "$p" ] || { info "$label" "path absent: $p"; return; }
  line=$(printf '%s\n' "$CAN" | python3 -I "$HERE/scan-host.py" --stamp "$STAMP" "--$mode" "$p" --root-timeout 60); rc=$?
  if [ "$rc" -gt 2 ] || [ -z "$line" ]; then say "FAIL  $label: scanner failed (exit $rc), nothing proven"; FAILS=$((FAILS + 1)); return; fi
  IFS=$'\t' read -r real _ hits nh fr br old sl fi so dv de ov ch to va sample <<< "$line"
  check "$label ($mode, $real): files whose contents contain the canary" "$hits" 0
  check "$label: entry names containing the canary" "$nh" 0
  info "$label: regular files examined in stated scope" "$fr ($br bytes)"
  info "$label: skipped by design, not read" "old (changed before the stamp) $old, symlink $sl, fifo $fi, socket $so, device $dv"
  [ "$va" -gt 0 ] && info "$label: vanished (listed, then gone before it was read; not UNVERIFIED, 551 v17 R2)" "$va; paths (redacted) in: $sample"
  if [ $((de + ov + ch + to)) -eq 0 ]; then info "$label: UNVERIFIED" "none (denied 0, oversize 0, changed 0, timeout 0)"
  else INCOMPLETE=$((INCOMPLETE + 1)); info "$label: UNVERIFIED (INCOMPLETE)" "denied $de, oversize $ov, changed $ch, timeout $to; paths (redacted): $sample"; fi
}
prefixed() { grep -caF -f <(printf '%s\n' "$PREFIX") || true; }                           # stdin: lines with the prefix
wexec() { "${D[@]}" exec -u node oc551-worker "$@"; }
rootread() { "${D[@]}" exec oc551-worker "$@"; }   # for /proc/1/environ (the gateway runs as node too; this is just explicit)
labelled() { [ "$("${D[@]}" inspect -f '{{index .Config.Labels "oc551"}}' "$1" 2>/dev/null)" = 1 ]; }
cleanup() {
  for p in "$ROUTE_PID" "$PS_PID" "$NPM_PID" "$LOG_PID" "$WAIT_PID"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done
  rm -f "$FLAG" "$FLAG".*; rm -rf "$SCAN_TMP"
  for c in oc551-worker oc551-edge; do labelled "$c" && "${D[@]}" rm -f "$c" >/dev/null 2>&1; done
  CAN=""
}
trap cleanup EXIT
trap 'exit 130' INT TERM

start_worker() {  # $1 = CANARY ("" or 1); phase1.sh waits for "stage 1 ok", fails on "refusing", and checks docker diff
  local o; if o=$(CANARY="$1" "$HERE/phase1.sh" worker 2>&1); then return 0; fi
  say "FAIL  worker start (CANARY=$1); phase1.sh said:"; printf '%s\n' "$o" | sed 's/^/        /' | tee -a "$OUT"   # no secret exists yet at start
  FAILS=$((FAILS + 1)); return 1
}
mem_checks() {  # $1 label, $2 container: before every stop (551 M3)
  check "$1: $2 HostConfig Memory == MemorySwap" "$("${D[@]}" inspect -f '{{if eq .HostConfig.Memory .HostConfig.MemorySwap}}equal{{else}}{{.HostConfig.Memory}}/{{.HostConfig.MemorySwap}}{{end}}' "$2")" equal
  check "$1: $2 memory.swap.current" "$("${D[@]}" exec "$2" cat /sys/fs/cgroup/memory.swap.current)" 0
  check "$1: $2 memory.events oom_kill" "$("${D[@]}" exec "$2" sh -c 'awk "\$1==\"oom_kill\"{print \$2}" /sys/fs/cgroup/memory.events')" 0
  info "$1: $2 memory.peak / memory.max (bytes)" "$("${D[@]}" exec "$2" sh -c 'echo "$(cat /sys/fs/cgroup/memory.peak) / $(cat /sys/fs/cgroup/memory.max)"')"
}
stop_worker() {
  mem_checks "${1:-stop}" oc551-worker
  "${D[@]}" stop -t 5 oc551-worker >/dev/null 2>&1
  for _ in $(seq 1 50); do "${D[@]}" inspect oc551-worker >/dev/null 2>&1 || return 0; sleep 0.2; done
  say "FAIL  worker still present after stop"; FAILS=$((FAILS + 1))
}
top_args() {  # the worker's process args via host-side docker top; fails (nonzero) if docker top fails. `-eo args` alone is
  # rejected by the daemon ("Couldn't find PID field in ps output"; canary 20261013T201424), so ask for pid,args and drop pid
  local o; o=$("${D[@]}" top oc551-worker -o pid,args 2>/dev/null) || return 1
  printf '%s\n' "$o" | tail -n +2 | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]+//'
}
connect_checks() {  # $1 label; stdin: edge log lines. 551 v20: every line parsed as JSON, counted by exact (op, target, verdict).
  # The parent's own engineering choice A (20:30:43, FAKE only; NOT user approval; user decision pending; not a REAL-run rule):
  # OpenClaw's post-start plugin-feed prewarm (clawhub.ai, no auth, no config gate at the pin) may appear as exactly ONE refused
  # CONNECT per gateway start. It is never on the allowlist. Startup model discovery is off (models.mode replace), so
  # api.anthropic.com:443 must be 0. Any other target, any CONNECT not refused, any plain-http request or any unparseable line FAILs.
  local c hub api other bad http unp
  c=$(python3 -I -c '
import json, sys
c = dict(hub=0, api=0, other=0, bad=0, http=0, unp=0)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        o = json.loads(line)
    except ValueError:
        c["unp"] += 1; continue
    if not isinstance(o, dict):
        c["unp"] += 1; continue
    op, t, v = o.get("op"), o.get("target"), o.get("verdict")
    if op == "http":
        c["http"] += 1; continue
    if op != "CONNECT":
        continue
    if v != "refused":
        c["bad"] += 1
    if t == "api.anthropic.com:443":
        c["api"] += 1
    elif t == "clawhub.ai:443":
        c["hub"] += v == "refused"
    else:
        c["other"] += 1
print(c["hub"], c["api"], c["other"], c["bad"], c["http"], c["unp"])') || { say "FAIL  $1: edge log classifier failed"; FAILS=$((FAILS + 1)); return; }
  read -r hub api other bad http unp <<< "$c"
  check "expected refusal (parent 20:30:43 engineering choice A, FAKE only; user decision pending; not a REAL-run rule): clawhub.ai:443 refused" "$hub" 1   # 551 W2, exact; exactly 1
  check "$1: CONNECT api.anthropic.com:443, any verdict" "$api" 0
  check "$1: CONNECT to any other target" "$other" 0
  check "$1: CONNECT not refused (allowed, upstream-error or other), any target" "$bad" 0
  check "$1: plain-http requests at the edge" "$http" 0
  check "$1: edge log lines that are not JSON objects" "$unp" 0
  return 0
}
sample_ps() {  # host ps and docker top while the fill runs; counts of the canary prefix only
  while [ -e "$FLAG" ]; do
    { ps -axww -o command= | prefixed; if t=$(top_args); then printf '%s\n' "$t" | prefixed; else echo ERR; fi; } | paste -sd' ' - >> "$FLAG.ps"
    sleep 0.05
  done
}
sample_npm() {  # npm processes in the worker, sampled every 0.2 s for as long as the flag exists
  while [ -e "$FLAG.npm-on" ]; do
    if t=$(top_args); then printf '%s\n' "$t" | grep -c '[n]pm' >> "$FLAG.npm"; printf '%s\n' "$t" | grep -cE '[o]penclaw.*gateway' >> "$FLAG.gw"
    else echo ERR >> "$FLAG.npm"; fi   # a failed sample is never a 0
    sleep 0.2
  done
}
browser_fill() {  # the real route opened by the real browser tool; then read the canary back from the tmpfs
  local fd line url r
  touch "$FLAG"; : > "$FLAG.ps"; sample_ps & PS_PID=$!
  fd=$(mktemp -d); mkfifo -m 600 "$fd/url"   # bash 3.2 has no coproc; a fifo keeps the route URL off disk
  FILL_TIMEOUT=60 python3 -I "$HERE/fill-route.py" oc551-worker > "$fd/url" & ROUTE_PID=$!
  exec 3< "$fd/url"; read -r line <&3; url="${line##* }"; rm -rf "$fd"
  r=$("$BROWSER" "$url" 2>/dev/null | paste -sd' ' -)
  wait "$ROUTE_PID" 2>/dev/null; ROUTE_PID=""; exec 3<&-
  rm -f "$FLAG"; wait "$PS_PID" 2>/dev/null; PS_PID=""
  check "fill via the browser route (status; inputs left in the page DOM)" "$r" "filled: yes dom-inputs: 0"
  check "host ps / docker top samples with the canary prefix (max)" "$(tr ' ' '\n' < "$FLAG.ps" | grep -v ERR | sort -n | tail -1)" 0
  check "docker top samples that failed during the fill" "$(grep -c ERR "$FLAG.ps")" 0
  info "ps samples during the fill" "$(wc -l < "$FLAG.ps" | tr -d ' ')"; rm -f "$FLAG.ps"
  CAN="$(wexec cat /run/secrets/model_key 2>/dev/null)"   # FAKE only (see the header)
  if printf '%s' "$CAN" | grep -qE '^sk-ant-canary-[0-9a-f]{48}$'; then say "ok    control: read-back has the page canary's shape"
  else CAN=""; say "FAIL  control: read-back is not a page canary; cleared, nothing scanned"; FAILS=$((FAILS + 1)); return; fi
  check "control: host scanner matcher finds the canary in memory, across chunks (never a disk file)" \
    "$(printf '%s\n' "$CAN" | python3 -I "$HERE/scan-host.py" --control)" "control hits 1"
}
container_scans() {  # $1 = label; $2 = check|info for /demo/state (gateway state is memory-only by design; a finding)
  cscan "$1: docker inspect worker" "${D[@]}" inspect oc551-worker
  cscan "$1: docker logs worker" "${D[@]}" logs oc551-worker
  local df; if df=$("${D[@]}" diff oc551-worker 2>/dev/null); then check "$1: docker diff worker (root fs changes)" "$(printf '%s' "$df" | grep -c .)" 0
  else say "FAIL  $1: docker diff worker: command failed, nothing proven"; FAILS=$((FAILS + 1)); fi   # a missing container is never a 0
  cscan "$1: canary copies in the /tmp tmpfs (exec tar stream, never to disk)" wexec tar -C /tmp -cf - .
  cscan "$1: canary copies in the /demo/io tmpfs (exec tar stream)" wexec tar -C /demo/io -cf - .
  if [ "$2" = check ]; then cscan "$1: canary copies in the /demo/state tmpfs (exec tar stream)" wexec tar -C /demo/state -cf - .
  else
    local st; st=$( { wexec tar -C /demo/state -cf - . 2>/dev/null | count; echo " ${PIPESTATUS[0]}"; } | tr -s ' \n' ' ')
    set -- "$1" $st
    if [ "${3:-x}" != 0 ]; then say "FAIL  $1: /demo/state tar failed (exit ${3:-?})"; FAILS=$((FAILS + 1))
    else info "$1: canary copies in the /demo/state tmpfs (finding; tmpfs, dies with the container)" "$2"; fi
  fi
}
host_scans() {  # $1 = label. Repo and audit folder in full; the shared temp dirs and Docker's host logs since the stamp
  say "      $1: host scans starting $(date +%H:%M:%S) (5 roots, at most 60 s each)"
  hscan "$1: repo" "$REPO" full
  hscan "$1: audit folder (receipts, logs)" "$AUD" full
  hscan "$1: /private/tmp" /private/tmp recent
  hscan "$1: \$TMPDIR" "${TMPDIR:-/private/tmp}" recent
  hscan "$1: Docker Desktop host logs" "$DDLOG" recent
  info "$1: not scannable from the host" "the Docker VM's own disk and swap, and dockerd/containerd/shim memory (owner accepted, option A)"
  say "      $1: host scans done $(date +%H:%M:%S)"
}
restart_empty() {  # d: after the stop, a fresh CANARY=1 start shows both memory mounts empty
  start_worker 1 || return
  check "$1: /run/secrets entries after restart" "$(wexec sh -c 'ls -A /run/secrets | wc -l')" 0
  check "$1: /demo/state files after restart" "$(wexec sh -c 'find /demo/state -type f | wc -l')" 0
  if [ "$1" = d ]; then  # on the fresh worker, with plain dummy values (not the canary): framing and exclusivity
    # M1 (operator 20:04): a stream too short to hold the end line is refused for any reason; a long one without it, exit 8
    check "M1: a 1-byte stream is refused" "$(printf 'x' | "$HERE/fill-key.sh" oc551-worker 2>/dev/null | grep -cE '^filled: no \(exit [1-9][0-9]*\)$')" 1
    check "M1: nothing published and no part left after it" "$(wexec sh -c 'ls -A /run/secrets | wc -l')" 0
    check "M1: a 64-byte stream with no end line is refused as truncated" "$(printf '%064d' 0 | "$HERE/fill-key.sh" oc551-worker 2>/dev/null)" "filled: no (exit 8)"
    check "M1: nothing published and no part left after that either" "$(wexec sh -c 'ls -A /run/secrets | wc -l')" 0
    printf 'y\nOC551-END\n' | "$HERE/fill-key.sh" oc551-worker > "$SCAN_TMP/f1" 2>/dev/null &
    printf 'z\nOC551-END\n' | "$HERE/fill-key.sh" oc551-worker > "$SCAN_TMP/f2" 2>/dev/null & wait
    check "M5: two parallel fills on a fresh worker" "$(cat "$SCAN_TMP/f1" "$SCAN_TMP/f2" | sort | paste -sd'|' -)" "filled: no (exit 4)|filled: yes"
    check "M5: exactly one model_key and no part left" "$(wexec sh -c 'ls -A /run/secrets | paste -sd" " -')" model_key
  fi
  stop_worker "$1"
}

if [ "${1:-}" = --selftest ]; then  # scanner logic only: no Docker, a fixed fake value, a throwaway receipt
  OUT="$(mktemp "$SCAN_TMP/selftest.XXXXXX")"; CAN="sk-ant-canary-$(printf '%048d' 0)"; T="$SCAN_TMP/tree"; mkdir -p "$T/locked"
  echo harmless > "$T/a.txt"; echo hidden > "$T/locked/b.txt"; chmod 000 "$T/locked"
  cscan "selftest: clean command" printf 'nothing here\n'
  EXPECT=1 cscan "selftest: command output containing the value" printf '%s\n' "$CAN"
  before=$FAILS; cscan "selftest: failing command" sh -c 'echo partial; exit 3'
  check "selftest: a failing command is a FAIL, not a 0" "$((FAILS - before))" 1; FAILS=$before
  hscan "selftest: tree with one unreadable dir" "$T"
  check "selftest: unreadable dir reported INCOMPLETE" "$(grep -c 'UNVERIFIED (INCOMPLETE)' "$OUT")" 1
  check "selftest: incomplete roots counted (blocks a plain PASS)" "$INCOMPLETE" 1
  check "selftest: scanner matcher control" "$(printf '%s\n' "$CAN" | python3 -I "$HERE/scan-host.py" --control)" "control hits 1"
  mkfifo "$T/pipe"; hscan "selftest: tree with a fifo (must not block)" "$T"   # second pass; the locked dir counts again
  check "selftest: fifo counted, scan returned" "$(grep -c 'selftest: tree with a fifo (must not block): skipped by design, not read = .*fifo 1,' "$OUT")" 1
  H='{"at":"t","op":"CONNECT","target":"clawhub.ai:443","verdict":"refused"}'; S='{"at":"t","listen":"x","allow":[]}'
  for case in "clawhub x1|PASS|$S\n$H" "clawhub x2|FAIL|$H\n$H" "clawhub x0|FAIL|$S" \
      "anthropic x1|FAIL|$H\n{\"op\":\"CONNECT\",\"target\":\"api.anthropic.com:443\",\"verdict\":\"refused\"}" \
      "other x1|FAIL|$H\n{\"op\":\"CONNECT\",\"target\":\"example.com:443\",\"verdict\":\"refused\"}" \
      "allowed x1|FAIL|{\"op\":\"CONNECT\",\"target\":\"clawhub.ai:443\",\"verdict\":\"allowed\"}" \
      "clawhub.ai:4430|FAIL|{\"op\":\"CONNECT\",\"target\":\"clawhub.ai:4430\",\"verdict\":\"refused\"}" \
      "xclawhub.ai:443|FAIL|{\"op\":\"CONNECT\",\"target\":\"xclawhub.ai:443\",\"verdict\":\"refused\"}" \
      "http line|FAIL|$H\n{\"op\":\"http\",\"verdict\":\"refused\",\"target\":\"x\"}" \
      "unparseable line|FAIL|$H\nnot json"; do
    IFS='|' read -r name want lines <<< "$case"; before=$FAILS
    connect_checks "selftest edge: $name" < <(printf '%b\n' "$lines") > /dev/null
    got=$([ "$FAILS" -gt "$before" ] && echo FAIL || echo PASS); FAILS=$before
    check "selftest: edge rule, $name" "$got" "$want"
  done
  chmod 700 "$T/locked"; [ "$FAILS" -eq 0 ] && echo "selftest: PASS" || echo "selftest: FAIL ($FAILS)"; exit "$FAILS"
fi

say "canary receipt $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$REPO" rev-parse --short HEAD); worker image $("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3 | cut -c8-19); edge image $("${D[@]}" image inspect -f '{{.Id}}' oc551-edge:1 | cut -c8-19)"
check "precondition: browser tool built" "$([ -x "$BROWSER" ] && echo yes)" yes
check "precondition: edge container present" "$("${D[@]}" ps -aq --filter name=^oc551-edge$ | wc -l | tr -d ' ')" 0
check "precondition: worker container present" "$("${D[@]}" ps -aq --filter name=^oc551-worker$ | wc -l | tr -d ' ')" 0
"$HERE/phase1.sh" net >/dev/null
check "precondition: worker image has no /run/secrets content baked in" "$("${D[@]}" run --rm --label oc551=1 --network none --entrypoint sh oc551-worker:2026.10.3 -c 'ls -A /run/secrets 2>/dev/null | wc -l')" 0
check "precondition: oc551-int is internal" "$("${D[@]}" network inspect -f '{{.Internal}}' oc551-int)" true
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (preconditions)"; exit 1; }

say "== steps a-e: CANARY=1 (the entrypoint stops after its stage 2 checks; no gateway)"
if start_worker 1; then
  for m in /run/secrets /demo/state /tmp /demo/io; do check "a: $m fstype" "$(wexec findmnt -no FSTYPE $m)" tmpfs; done
  check "a: /run/secrets mode owner" "$(wexec stat -c '%a %U' /run/secrets)" "700 node"
  check "e: cgroup memory.swap.max (no swap for anon or tmpfs pages)" "$(wexec cat /sys/fs/cgroup/memory.swap.max)" 0
  info "e: VM swap (why the cgroup gate is needed)" "$(wexec grep SwapTotal /proc/meminfo | tr -s ' ')"
  browser_fill
  check "b: model_key mode owner" "$(wexec stat -c '%a %U' /run/secrets/model_key)" "600 node"
  check "b: model_key.part.* files left" "$(wexec sh -c 'ls /run/secrets | grep -c "^model_key\.part\."' || true)" 0
  sleep 1.5
  check "b: entrypoint accepted the fill" "$("${D[@]}" logs oc551-worker 2>&1 | grep -c 'canary stage 2 ok')" 1
  EXPECT=1 cscan "control: the tar scan path sees the canary in /run/secrets" wexec tar -C /run/secrets -cf - .
  container_scans "c" check
  host_scans "c"
  check "single use: a second fill is refused" "$(printf 'x\nOC551-END\n' | "$HERE/fill-key.sh" oc551-worker 2>/dev/null)" "filled: no (exit 4)"
  stop_worker
  host_scans "d after stop"
  restart_empty "d"
fi
CAN=""

say "== stage 2b: the gateway runs with the canary as its key for 30 s; no agent turn; edge refuses every CONNECT"
if eo=$(EDGE_ALLOW="" "$HERE/phase1.sh" edge 2>&1); then
  check "2b: edge allowlist is empty" "$("${D[@]}" logs oc551-edge 2>&1 | grep -cF '"allow":[]')" 1
  if start_worker ""; then
    touch "$FLAG.npm-on"; : > "$FLAG.npm"; : > "$FLAG.gw"; sample_npm & NPM_PID=$!
    # --rm deletes a dead worker and its logs, so record its exit code and a redacted copy of its log as it runs. The
    # redaction is by pattern (any sk-ant- token, any token= value), so it needs no knowledge of the value.
    "${D[@]}" wait oc551-worker > "$SCAN_TMP/gw-exit" 2>/dev/null & WAIT_PID=$!
    "${D[@]}" logs -f oc551-worker 2>&1 | awk '{ n += gsub(/sk-ant-[A-Za-z0-9_-]+/, "<REDACTED-KEY>"); n += gsub(/token=[^ &"]+/, "token=<REDACTED>"); print; fflush() }
      END { print "redacted tokens: " n + 0 > "/dev/stderr" }' > "$SCAN_TMP/gw-log" 2> "$SCAN_TMP/gw-redacted" & LOG_PID=$!
    browser_fill
    for _ in $(seq 1 50); do "${D[@]}" logs oc551-worker 2>&1 | grep -q 'starting gateway' && break; sleep 0.2; done
    check "2b: entrypoint started the gateway" "$("${D[@]}" logs oc551-worker 2>&1 | grep -c 'stage 2 ok; starting gateway')" 1
    sleep 30
    GW_UP=$("${D[@]}" inspect -f '{{.State.Running}}' oc551-worker 2>/dev/null)
    check "2b: gateway still running after 30 s" "$GW_UP" true
    check "2b: gateway log lines '[gateway] ready' (redacted copy)" "$(grep -cE '\[gateway\] ready$' "$SCAN_TMP/gw-log")" 1   # 551 v14/v15 V1
    check "2b: gateway log lines saying start blocked" "$(grep -ci 'start blocked' "$SCAN_TMP/gw-log")" 0
  fi
  if [ "${GW_UP:-}" != true ] && [ -n "$WAIT_PID" ]; then   # the gateway died: say why (exit code, redacted log), skip in-container checks
    for _ in $(seq 1 25); do kill -0 "$WAIT_PID" 2>/dev/null || break; sleep 0.2; done
    for _ in $(seq 1 25); do kill -0 "$LOG_PID" 2>/dev/null || break; sleep 0.2; done
    info "2b: worker exit code" "$(cat "$SCAN_TMP/gw-exit" 2>/dev/null || echo unknown)"
    tail -30 "$SCAN_TMP/gw-log" 2>/dev/null | sed 's/^/        /' | tee -a "$OUT"
    rm -f "$FLAG.npm-on"; wait "$NPM_PID" 2>/dev/null; NPM_PID=""; rm -f "$FLAG.npm" "$FLAG.gw"
    say "      2b: in-container checks not run (no worker); host scans still run"
    host_scans "2b after the gateway died"
  elif [ "${GW_UP:-}" = true ]; then
    # 551 v13: "Running" alone is not proof. The gateway process must exist and answer its own health check.
    if procs=$(top_args); then
      check "2b: docker top shows the openclaw gateway process" "$(printf '%s\n' "$procs" | grep -cE '[o]penclaw.*gateway' | awk '{print ($1 > 0) ? "yes" : "no"}')" yes
      info "2b: worker processes" "$(printf '%s\n' "$procs" | cut -c1-60 | paste -sd';' -)"
    else say "FAIL  2b: docker top failed, gateway process not shown"; FAILS=$((FAILS + 1)); fi
    hj=$(wexec sh -c 'OPENCLAW_GATEWAY_TOKEN="$(cat /run/secrets/gateway_token)" openclaw health --json --timeout 5000' 2>/dev/null); hrc=$?
    check "2b: openclaw health exit" "$hrc" 0
    check "2b: openclaw health top-level ok" "$(printf '%s' "$hj" | python3 -I -c 'import json, sys
try: print(json.load(sys.stdin).get("ok") is True)
except Exception: print("unparseable")')" True
    check "2b: canary in the health output" "$(printf '%s\n' "$hj" | count)" 0; hj=""
    check "2b: worker networks" "$("${D[@]}" inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' oc551-worker | xargs)" oc551-int
    EXPECT=1 cscan "control: canary in the gateway's process env (pid 1)" rootread sh -c "tr '\\0' '\\n' < /proc/1/environ"
    info "2b: /demo/state files" "$(wexec sh -c 'find /demo/state -type f | sed "s|^/demo/state/||" | head -20 | paste -sd" " -')"
    container_scans "2b" info
    rm -f "$FLAG.npm-on"; wait "$NPM_PID" 2>/dev/null; NPM_PID=""
    check "2b: npm processes in the worker (sampled every 0.2 s over the whole stage, $(wc -l < "$FLAG.npm" | tr -d ' ') samples; max)" \
      "$(grep -v ERR "$FLAG.npm" | sort -n | tail -1)" 0
    check "2b: npm samples that failed (docker top error)" "$(grep -c ERR "$FLAG.npm")" 0
    check "2b: positive control: the same samples show the gateway process (551 v17 R1)" "$(sort -n "$FLAG.gw" | tail -1 | awk '{print ($1 > 0) ? "yes" : "no"}')" yes
    rm -f "$FLAG.npm" "$FLAG.gw"
    stop_worker "2b"
    host_scans "2b after stop"
  fi
  # the edge checks run whether or not the gateway lived (a dead gateway could still have tried to connect first)
  connect_checks "2b" < <("${D[@]}" logs oc551-edge 2>&1)   # redirect, not a pipe: a pipe would run it in a subshell and lose FAILS
  ct=$("${D[@]}" logs oc551-edge 2>&1 | grep '"op":"CONNECT"' | grep -o '"target":"[^"]*"' | sort | uniq -c | paste -sd' ' -)
  [ -n "$ct" ] && info "2b: CONNECT targets (host:port only)" "$ct"
  info "2b: tool-forward requests at the edge" "$("${D[@]}" logs oc551-edge 2>&1 | grep -c '"op":"tool"' || true)"
  cscan "2b: docker inspect edge" "${D[@]}" inspect oc551-edge
  cscan "2b: docker logs edge" "${D[@]}" logs oc551-edge
  mem_checks "2b" oc551-edge
  if [ -n "$WAIT_PID" ]; then
    wait "$WAIT_PID" 2>/dev/null; WAIT_PID=""; wait "$LOG_PID" 2>/dev/null; LOG_PID=""   # the redactor writes its count at stream end
    # 551 v15 V2: redaction must not hide a leak; any key-shaped or token= value in the gateway's output is a FAIL (both paths)
    check "2b: key-shaped or token= values redacted from the gateway log" "$(sed -n 's/^redacted tokens: //p' "$SCAN_TMP/gw-redacted" 2>/dev/null)" 0
    restart_empty "2b"
  fi
  "${D[@]}" stop -t 5 oc551-edge >/dev/null 2>&1
  for _ in $(seq 1 25); do "${D[@]}" inspect oc551-edge >/dev/null 2>&1 || break; sleep 0.2; done
  check "2b: edge gone after its stop (--rm)" "$("${D[@]}" ps -aq --filter name=^oc551-edge$ | wc -l | tr -d ' ')" 0
else
  say "FAIL  edge start with an empty allowlist; phase1.sh said:"; printf '%s\n' "$eo" | sed 's/^/        /' | tee -a "$OUT"; FAILS=$((FAILS + 1))
fi
CAN=""

sleep 1   # BEFORE cleanup (551): proves every stop plus --rm removed its container; a leftover here is a FAIL
check "end: oc551 containers left before cleanup" "$("${D[@]}" ps -aq --filter label=oc551=1 | wc -l | tr -d ' ')" 0
cleanup   # the same cleanup the EXIT trap runs
for _ in $(seq 1 25); do [ "$("${D[@]}" ps -aq --filter label=oc551=1 | wc -l | tr -d ' ')" = 0 ] && break; sleep 0.2; done
check "end: oc551 containers left after cleanup" "$("${D[@]}" ps -aq --filter label=oc551=1 | wc -l | tr -d ' ')" 0
echo "receipt: $OUT"
if [ "$FAILS" -ne 0 ]; then say "RESULT: FAIL ($FAILS checks; $INCOMPLETE roots incomplete)"; exit 1; fi
if [ "$INCOMPLETE" -ne 0 ]; then say "RESULT: PASS-UNVERIFIED ($INCOMPLETE roots incomplete; each listed path needs acceptance)"; exit 2; fi
say "RESULT: PASS"; exit 0
