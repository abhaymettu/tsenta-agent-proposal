#!/bin/bash
# G-h effective-tools check with NO model call (551 v27). Run after the fill and before the first agent turn, with the
# gateway up. It reads only the gateway token (inside the worker, into the env of one CLI process; never argv) and calls
# read-only gateway methods. Nothing here creates a session or submits a prompt.
# (1) sessions.list: record the session keys; expect agent:main:main (not assumed). With no key, (2) is BLOCKED; a key is
#     never created with a turn.
# (2) tools.effective for agentId main and that key: no non-tsenta__ tool in groups; toolAccess present; session_status,
#     gateway and presence status excluded with a reason of kind deny; profile and the active toolAccess profile minimal; notices
#     listed by id and severity. Ids, statuses and reason kinds only.
# (3a) tools.catalog: no group or tool with source "plugin" or "channel" (551 v34; the catalog carries no pluginId).
# (3b) `openclaw plugins list --enabled --json` in the worker as node: the enabled plugin ids are EXACTLY ["anthropic"];
#      an unknown output shape FAILs.
# (4) Separate stage, `openclaw mcp probe tsenta`: the tool names must EQUAL the fixture's published list (core/engine.py
#     TOOLS, hardcoded below). It needs the fixture bearer at the edge (no token gives 503), so without it the stage is
#     BLOCKED, not FAIL.
# (5) Key-shaped tokens (sk-ant-) counted by pattern in every output: 0.
# Field paths follow 551 v31 (the pinned source's tools.effective result); a missing field FAILs (never assumed clean). Outputs are summarized by
# python3 -I; raw JSON is never printed.
# --pre-session: before 9.5 step 2 no session exists, and (2) needs one (551 v34: never sessions.create here, since it can
# carry an initial turn), so (2) is DEFERRED and not counted; without the flag a missing key is BLOCKED.
# --post-ping (551 v35): right after 9.5 step 2. sessions.list must hold exactly one key ending :tsenta-demo-g0-P95, and
# (2) runs on it with the full rule: the only group is mcp and its tools EQUAL tsenta__ + the 14 fixture names;
# session_status, gateway and presence excluded with deny; profile minimal; a warning notice FAILs; the notice
# mcp-not-yet-connected means BLOCKED.
# Usage: openclaw/tools-check.sh [--pre-session | --post-ping]   (receipt: ~/audit/tsenta-openclaw-1013/TOOLS-CHECK-<time>.txt; exit 0 PASS, 1 FAIL,
# 3 BLOCKED (a stage could not run))
set -uo pipefail
D=(docker --context desktop-linux)
AUD="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$AUD"
OUT="$AUD/TOOLS-CHECK-$(date +%Y%m%dT%H%M%S).txt"
FIXTURE_TOOLS="ats_status ats_submit draft_create draft_revise mail_list mail_read mail_send_draft profile_get record_get record_search request_approval resume_variant save_preference status_summary"
FAILS=0; BLOCKED=0; PRE=0; POST=0; [ "${1:-}" = --pre-session ] && PRE=1; [ "${1:-}" = --post-ping ] && POST=1
say() { echo "$*" | tee -a "$OUT"; }
check() { if [ "$2" = "$3" ]; then say "ok    $1 = $2"; else say "FAIL  $1 = $2 (want $3)"; FAILS=$((FAILS + 1)); fi; }
info() { say "info  $1 = $2"; }
gw() {  # $1 method, $2 params JSON; prints the JSON response; the token stays inside the worker
  "${D[@]}" exec -u node oc551-worker sh -c 'OPENCLAW_GATEWAY_TOKEN="$(cat /run/secrets/gateway_token)" exec openclaw gateway call "$0" --params "$1" --json' "$1" "$2" 2>&1
}
keys() { printf '%s\n' "$1" | grep -c 'sk-ant-'; true; }
py() { python3 -I -c "$1"; }   # stdin: one JSON document

say "G-h tools check $(date '+%Y-%m-%dT%H:%M:%S%z'); repo $(git -C "$(dirname "$0")/.." rev-parse --short HEAD); worker image $("${D[@]}" image inspect -f '{{.Id}}' oc551-worker:2026.10.3 | cut -c8-19)"
check "worker running" "$("${D[@]}" inspect -f '{{.State.Running}}' oc551-worker 2>/dev/null)" true
[ "$FAILS" -eq 0 ] || { say "RESULT: FAIL (no worker)"; exit 1; }

say "== (1) sessions.list"
sl=$(gw sessions.list '{}'); rc=$?
check "sessions.list exit" "$rc" 0
check "sessions.list key-shaped tokens" "$(keys "$sl")" 0
skeys=$(printf '%s' "$sl" | py '
import json, sys
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("key", "sessionKey") and isinstance(v, str): yield v
            else: yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)
try: print(" ".join(sorted(set(walk(json.load(sys.stdin))))) or "none")
except Exception: print("unparseable")')
info "session keys" "$skeys"
SKEY=""
if [ "$POST" = 1 ]; then
  pk=$(printf '%s\n' $skeys | grep -iE ':tsenta-demo-g0-p95$'); true   # the Gateway lower-cases keys (ping 21:16)
  check "(1) session keys ending :tsenta-demo-g0-p95 (any case)" "$(printf '%s' "$pk" | grep -c .)" 1
  [ "$(printf '%s' "$pk" | grep -c .)" = 1 ] && SKEY="$pk"
else
  case " $skeys " in *" agent:main:main "*) SKEY=agent:main:main ;; esac
  [ -n "$SKEY" ] || { set -- $skeys; case "${1:-none}" in none|unparseable) ;; agent:main:*) SKEY="$1" ;; esac; }
fi

say "== (2) tools.effective"
if [ -z "$SKEY" ] && [ "$PRE" = 1 ]; then say "DEFERRED (2): no session yet; runs after 9.5 step 2 creates it (551 v34)"
elif [ -z "$SKEY" ] && [ "$POST" = 1 ]; then say "FAIL  (2): no single ping session key"; FAILS=$((FAILS + 1))
elif [ -z "$SKEY" ]; then say "BLOCKED  (2): no main session key (a key is never created with a turn)"; BLOCKED=1
else
  te=$(gw tools.effective "{\"agentId\":\"main\",\"sessionKey\":\"$SKEY\"}"); rc=$?
  check "tools.effective exit" "$rc" 0
  check "tools.effective key-shaped tokens" "$(keys "$te")" 0
  # field paths from 551 v31 (the pinned source's tools.effective result): {agentId, profile, groups[{id, label, source,
  # tools[{id}]}], notices[{id, severity, message, servers}], toolAccess{tools[{id, status, reasons[{kind, label}]}],
  # profiles[{profile, source, active}], checked}}
  sum=$(printf '%s' "$te" | py '
import json, sys
try: d = json.load(sys.stdin)
except Exception: print("unparseable"); sys.exit()
if not isinstance(d, dict): print("unparseable"); sys.exit()
groups, acc = d.get("groups"), d.get("toolAccess")
ids = [t.get("id") for g in (groups or []) if isinstance(g, dict) for t in (g.get("tools") or []) if isinstance(t, dict)]
nonmcp = sorted(str(i) for i in ids if not str(i).startswith("tsenta__"))
tools = {t.get("id"): t for t in ((acc or {}).get("tools") or []) if isinstance(t, dict)} if isinstance(acc, dict) else {}
def denied(tid):
    t = tools.get(tid) or {}
    return "yes" if t.get("status") == "excluded" and any(isinstance(r, dict) and r.get("kind") == "deny" for r in t.get("reasons") or []) else "no"
active = [p.get("profile") for p in ((acc or {}).get("profiles") or []) if isinstance(p, dict) and p.get("active")] if isinstance(acc, dict) else []
excl = sorted("%s: %s (%s)" % (k, t.get("status"), ",".join(str(r.get("kind")) for r in t.get("reasons") or [] if isinstance(r, dict))) for k, t in tools.items() if t.get("status") != "allowed")
print("groups", "missing" if not isinstance(groups, list) else len(nonmcp))
print("nonmcp", " ".join(nonmcp) or "none")
print("toolAccess", "present" if isinstance(acc, dict) else "missing")
print("denied-session_status", denied("session_status"))
print("denied-gateway", denied("gateway"))
print("denied-presence", denied("presence"))
print("denied", "; ".join(excl)[:600] or "none")
print("profile", d.get("profile"))
print("active-profile", " ".join(map(str, active)) or "none")
print("allowed", " ".join(sorted(str(k) for k, t in tools.items() if t.get("status") == "allowed")) or "none")
print("notices", " ".join("%s/%s" % (n.get("id"), n.get("severity")) for n in d.get("notices") or [] if isinstance(n, dict)) or "none")
ns = [n for n in d.get("notices") or [] if isinstance(n, dict)]
print("notyet", "yes" if any(n.get("id") == "mcp-not-yet-connected" for n in ns) else "no")
print("warnings", sum(1 for n in ns if str(n.get("severity")).lower() in ("warning", "warn")))
print("groupids", " ".join(sorted(str(g.get("id")) for g in groups or [] if isinstance(g, dict))) or "none")
print("mcptools", " ".join(sorted(str(t.get("id")) for g in groups or [] if isinstance(g, dict) and g.get("id") == "mcp" for t in g.get("tools") or [] if isinstance(t, dict))) or "none")')
  v() { printf '%s\n' "$sum" | sed -n "s/^$1 //p" | head -1; }
  check "(2) non-MCP tools in groups" "$(v groups)" 0
  info "(2) non-MCP tool ids" "$(v nonmcp)"
  check "(2) toolAccess" "$(v toolAccess)" present
  check "(2) session_status excluded with a reason of kind deny" "$(v denied-session_status)" yes
  check "(2) gateway excluded with a reason of kind deny" "$(v denied-gateway)" yes
  check "(2) presence excluded with a reason of kind deny (551 v32 T1)" "$(v denied-presence)" yes
  info "(2) tools not allowed: id: status (reason kinds)" "$(v denied)"
  info "(2) tools allowed" "$(v allowed)"
  check "(2) profile" "$(v profile)" minimal
  check "(2) active profile in toolAccess.profiles" "$(v active-profile)" minimal
  info "(2) notices (id/severity)" "$(v notices)"
  if [ "$POST" = 1 ]; then
    if [ "$(v notyet)" = yes ]; then say "BLOCKED  (2): notice mcp-not-yet-connected (MCP tools not loaded yet)"; BLOCKED=1
    else
      check "(2) groups" "$(v groupids)" mcp
      check "(2) mcp group tools equal tsenta__ + the 14 fixture names" "$(v mcptools)" "$(for t in $FIXTURE_TOOLS; do printf 'tsenta__%s ' "$t"; done | sed 's/ $//')"
      check "(2) warning notices" "$(v warnings)" 0
    fi
  fi
fi

say "== (3) tools.catalog and enabled plugins"
tc=$(gw tools.catalog '{"agentId":"main","includePlugins":true}'); rc=$?
check "tools.catalog exit" "$rc" 0
check "tools.catalog key-shaped tokens" "$(keys "$tc")" 0
check "(3a) catalog groups or tools with source plugin or channel" "$(printf '%s' "$tc" | py '
import json, sys
try: d = json.load(sys.stdin)
except Exception: print("unparseable"); sys.exit()
groups = d.get("groups") if isinstance(d, dict) else None
if not isinstance(groups, list): print("missing"); sys.exit()
bad = [g for g in groups if not isinstance(g, dict) or g.get("source") in ("plugin", "channel")]
bad += [t for g in groups if isinstance(g, dict) for t in g.get("tools") or [] if not isinstance(t, dict) or t.get("source") in ("plugin", "channel")]
print(len(bad))')" 0
pl=$("${D[@]}" exec -u node oc551-worker sh -c 'OPENCLAW_GATEWAY_TOKEN="$(cat /run/secrets/gateway_token)" exec openclaw plugins list --enabled --json' 2>&1); rc=$?
check "plugins list exit" "$rc" 0
check "plugins list key-shaped tokens" "$(keys "$pl")" 0
check "(3b) enabled plugin ids" "$(printf '%s' "$pl" | py '
import json, sys
try: d = json.load(sys.stdin)
except Exception: print("unparseable"); sys.exit()
items = d if isinstance(d, list) else d.get("plugins") if isinstance(d, dict) else None
if not isinstance(items, list) or not all(isinstance(p, dict) and isinstance(p.get("id"), str) for p in items): print("unknown shape"); sys.exit()
print(json.dumps(sorted(p["id"] for p in items)))')" '["anthropic"]'

say "== (4) mcp probe tsenta (needs the fixture bearer at the edge)"
mp=$("${D[@]}" exec -u node oc551-worker sh -c 'OPENCLAW_GATEWAY_TOKEN="$(cat /run/secrets/gateway_token)" exec openclaw mcp probe tsenta --json' 2>&1); rc=$?
check "mcp probe key-shaped tokens" "$(keys "$mp")" 0
names=$(printf '%s' "$mp" | py '
import json, sys
try: d = json.load(sys.stdin)
except Exception: print("unparseable"); sys.exit()
tools = d.get("tools") if isinstance(d, dict) else None
print(" ".join(sorted(t.get("name", "") if isinstance(t, dict) else str(t) for t in tools)) if isinstance(tools, list) else "missing")')
if [ "$rc" != 0 ] || [ "$names" = missing ] || [ "$names" = unparseable ]; then
  if printf '%s' "$mp" | grep -q '503'; then say "BLOCKED  (4): the edge has no fixture bearer (503); not a FAIL"; BLOCKED=1
  else say "FAIL  (4): mcp probe failed (exit $rc, tools $names)"; FAILS=$((FAILS + 1)); fi
else
  # the probe reports the names the agent sees: the server name prefix tsenta__ plus the fixture's published name
  check "(4) tsenta tool names equal tsenta__ + the fixture's published list" "$names" "$(for t in $FIXTURE_TOOLS; do printf 'tsenta__%s ' "$t"; done | sed 's/ $//')"
fi

if [ "$FAILS" -gt 0 ]; then say "RESULT: FAIL ($FAILS checks)"; rc=1
elif [ "$BLOCKED" -gt 0 ]; then say "RESULT: BLOCKED (a stage could not run; see above)"; rc=3
else say "RESULT: PASS"; rc=0; fi
say "receipt: $OUT"
exit "$rc"
