#!/bin/sh
# Phase 1 (551 contract s9.6): reversible static install. No model key, no OpenClaw process, no agent.
# Every object is named oc551-* and labelled oc551=1; `phase1.sh reset` removes exactly those.
# Usage: openclaw/phase1.sh lock|build|audit|net|edge|worker|isolation|reset
set -eu
D="docker --context desktop-linux"
HERE="$(cd "$(dirname "$0")" && pwd)"
BASE=node:26.10.0-bookworm-slim@sha256:3ffc19ea878019d9e9ae8971732ad4a03cda44f167107173174b60ed7c65bed3
TGZ=${OPENCLAW_TGZ:-openclaw-2026.10.3.tgz}   # the verified upstream tarball
TGZ_SHA=761685d010d96645d1deabe19299ecde263eac3f2489a17322f48c461a1130a5
CTX="${TSENTA_AUDIT_DIR:-$PWD/run/audit}/build-ctx"   # under run/ (gitignored) by default: the 103 MB tarball never enters git
L="--label oc551=1"

context() {
  rm -rf "$CTX" && mkdir -p "$CTX"
  cp "$TGZ" "$CTX/" && (cd "$CTX" && echo "$TGZ_SHA  openclaw-2026.10.3.tgz" | shasum -a 256 -c -)
  cp "$HERE"/Dockerfile.worker "$HERE"/Dockerfile.edge "$HERE"/edge.mjs "$HERE"/entrypoint.sh "$HERE"/agent-turn.sh \
     "$HERE"/license-scan.mjs "$HERE"/openclaw.json5 "$HERE"/worker-package.json "$HERE"/lifecycle-complete.sh "$CTX/"
  [ -f "$HERE/worker-package-lock.json" ] && cp "$HERE/worker-package-lock.json" "$CTX/"
  return 0
}

case "${1:-}" in
  lock)   # resolve the transitive tree once, without installing or running any package script; commit the result
    context
    $D pull -q "$BASE" >/dev/null
    $D image inspect "$BASE" --format '{{index .RepoDigests 0}} {{.Os}}/{{.Architecture}} {{.Id}}'
    $D run --rm $L -v "$CTX:/w" -w /w "$BASE" sh -c 'cp worker-package.json package.json && npm install --package-lock-only --ignore-scripts --no-audit --no-fund >/dev/null && cp package-lock.json worker-package-lock.json'
    cp "$CTX/worker-package-lock.json" "$HERE/worker-package-lock.json"
    echo "lock: $(grep -c '"resolved"' "$HERE/worker-package-lock.json") resolved packages" ;;
  build)
    [ -f "$HERE/worker-package-lock.json" ] || { echo "run lock first" >&2; exit 2; }
    context
    $D build -q $L -f "$CTX/Dockerfile.worker" -t oc551-worker:2026.10.3 "$CTX"
    $D build -q $L -f "$CTX/Dockerfile.edge" -t oc551-edge:1 "$CTX"
    $D run --rm $L --network none --entrypoint openclaw oc551-worker:2026.10.3 --version ;;
  audit)  # npm audit needs the registry; this throwaway container runs no OpenClaw code. Exit 1 only means findings, so
          # the JSON's metadata is authoritative: a missing metadata block or an error object fails the step.
    A="${TSENTA_AUDIT_DIR:-$PWD/run/audit}"; mkdir -p "$A"
    set +e; $D run --rm $L --entrypoint sh oc551-worker:2026.10.3 -c 'cd /opt/openclaw && npm audit --omit=dev --json' > "$A/npm-audit.json"; rc=$?; set -e
    python3 -c "import json,sys;a=json.load(open('$A/npm-audit.json'));m=a.get('metadata',{}).get('vulnerabilities');sys.exit('audit invalid: '+json.dumps(a.get('error'))) if a.get('error') or m is None else print('audit exit $rc', m)"
    $D run --rm $L --network none --entrypoint node oc551-worker:2026.10.3 /opt/demo/license-scan.mjs /opt/openclaw/node_modules > "$A/license-scan.json"
    python3 -c "import json;l=json.load(open('$A/license-scan.json'));print('licenses', l['total'], 'needs review', len(l['review']))" ;;
  net)
    $D network inspect oc551-int >/dev/null 2>&1 || $D network create $L --internal oc551-int >/dev/null
    $D network inspect oc551-ext >/dev/null 2>&1 || $D network create $L oc551-ext >/dev/null
    $D network ls --filter label=oc551=1 --format '{{.Name}} internal={{.Internal}}' ;;
  edge)   # the edge's /run/secrets is tmpfs, 0700, owned by node; the core pushes the MCP bearer. The daemon rejects tmpfs
          # noswap and the VM has a swap file, so swap is off per container: equal --memory and --memory-swap gives cgroup2
          # memory.swap.max = 0, which keeps anon AND tmpfs pages out of swap (551 C1). EDGE_ALLOW may be set empty (canary).
    $D rm -f oc551-edge >/dev/null 2>&1 || true
    $D run -d --rm $L --name oc551-edge --network oc551-int --read-only --cap-drop ALL --security-opt no-new-privileges \
      --memory 128m --memory-swap 128m \
      --tmpfs /run/secrets:rw,noexec,nosuid,nodev,size=64k,mode=0700,uid=1000,gid=1000 \
      -e EDGE_ALLOW="${EDGE_ALLOW-api.anthropic.com:443}" -e TOOL_UPSTREAM=http://host.docker.internal:8550/mcp oc551-edge:1 >/dev/null
    i=0; until [ "$($D logs oc551-edge 2>&1 | grep -c '"op":"start"')" -ge 2 ]; do   # both listeners bound to the int address
      i=$((i + 1)); [ "$i" -le 50 ] || { echo "edge did not start" >&2; $D logs oc551-edge >&2; exit 1; }; sleep 0.2; done
    $D network connect oc551-ext oc551-edge   # egress leg, added only after the listeners bound
    $D exec oc551-edge sh -c '
      t=$(findmnt -no FSTYPE /run/secrets); m=$(stat -c "%a %U" /run/secrets); w=$(cat /sys/fs/cgroup/memory.swap.max)
      echo "fstype=$t mode=$m memory.swap.max=$w"
      [ "$t" = tmpfs ] && [ "$m" = "700 node" ] && [ "$w" = 0 ]' \
      || { echo "edge /run/secrets is not tmpfs + 0700 node with memory.swap.max 0; stopping it" >&2; $D rm -f oc551-edge >/dev/null; exit 1; }
    $D logs oc551-edge 2>&1 | grep '"op":"start"' ;;
  worker) # 551 s9.3/s9.4: oc551-int only (its only peer is the edge), read-only root, no capabilities, no secret in env or
          # argv. /run/secrets is a 0700 tmpfs owned by node; swap is off by cgroup (equal --memory/--memory-swap, 551 C1);
          # the entrypoint gates on both, then waits for the fill.
          # /demo/state (OPENCLAW_STATE_DIR and HOME) is a tmpfs too (551 P1): whatever OpenClaw persists there,
          # including anything derived from env credentials, dies with the container. The host core owns persistence.
          # CANARY=1 stops after the stage 2 checks (no gateway) for the memory-only proof.
    $D rm -f oc551-worker >/dev/null 2>&1 || true
    $D run -d --rm $L --name oc551-worker --network oc551-int --read-only --cap-drop ALL --security-opt no-new-privileges \
      --memory 2g --memory-swap 2g \
      --tmpfs /run/secrets:rw,noexec,nosuid,nodev,size=64k,mode=0700,uid=1000,gid=1000 \
      --tmpfs /tmp:rw,nosuid,nodev,size=64m,mode=1777 --tmpfs /demo/io:rw,nosuid,nodev,size=1m,mode=0700,uid=1000,gid=1000 \
      --tmpfs /demo/state:rw,nosuid,nodev,size=256m,mode=0700,uid=1000,gid=1000 -e HOME=/demo/state/home -e CANARY="${CANARY:-}" oc551-worker:2026.10.3 >/dev/null
    i=0; until $D logs oc551-worker 2>&1 | grep -q 'stage 1 ok'; do   # bounded; a refusal fails at once (551 C7)
      if $D logs oc551-worker 2>&1 | grep -q 'refusing' || ! $D inspect oc551-worker >/dev/null 2>&1; then echo "worker refused:" >&2; $D logs oc551-worker 2>&1 | tail -3 >&2; $D rm -f oc551-worker >/dev/null 2>&1; exit 1; fi
      i=$((i + 1)); [ "$i" -le 50 ] || { echo "worker did not reach stage 1" >&2; $D rm -f oc551-worker >/dev/null 2>&1; exit 1; }; sleep 0.2; done
    d=$($D diff oc551-worker)   # any failed gate removes the worker, so nothing is left behind (canary 19:38)
    [ -z "$d" ] || { echo "worker root filesystem changed (docker diff not empty):" >&2; echo "$d" >&2; $D rm -f oc551-worker >/dev/null 2>&1; exit 1; }
    $D logs oc551-worker 2>&1 | tail -2 ;;
  isolation)  # F4: a container on the default bridge cannot reach the edge by name or by any of its IPs
    for ip in $($D inspect oc551-edge --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}'); do
      $D run --rm $L "$BASE" node -e "const s=require('net').connect(8560,'$ip');s.setTimeout(3000);s.on('connect',()=>{console.log('REACHABLE $ip');process.exit(1)});s.on('error',e=>{console.log('unreachable $ip',e.code);process.exit(0)});s.on('timeout',()=>{console.log('unreachable $ip timeout');process.exit(0)})"
    done
    $D run --rm $L "$BASE" node -e "require('dns').lookup('oc551-edge',e=>{console.log(e?'name not resolvable from default bridge':'NAME RESOLVES');process.exit(e?0:1)})"
    $D run --rm $L --network oc551-ext "$BASE" node -e "const s=require('net').connect(8560,'oc551-edge');s.setTimeout(3000);s.on('connect',()=>{console.log('REACHABLE from oc551-ext');process.exit(1)});s.on('error',e=>{console.log('oc551-ext leg refused',e.code);process.exit(0)});s.on('timeout',()=>{console.log('oc551-ext leg timeout');process.exit(0)})" ;;
  reset)  # only these explicit names, and only if each carries the oc551=1 label
    for c in oc551-worker oc551-edge; do
      [ "$($D inspect -f '{{index .Config.Labels "oc551"}}' "$c" 2>/dev/null)" = 1 ] && $D rm -f "$c" >/dev/null && echo "removed container $c"
    done
    for n in oc551-int oc551-ext; do
      [ "$($D network inspect -f '{{index .Labels "oc551"}}' "$n" 2>/dev/null)" = 1 ] && $D network rm "$n" >/dev/null && echo "removed network $n"
    done
    for i in oc551-worker:2026.10.3 oc551-edge:1; do
      [ "$($D image inspect -f '{{index .Config.Labels "oc551"}}' "$i" 2>/dev/null)" = 1 ] && $D image rm "$i" >/dev/null && echo "removed image $i"
    done
    echo "reset done" ;;
  *) echo "usage: $0 lock|build|audit|net|edge|worker|isolation|reset" >&2; exit 2 ;;
esac
