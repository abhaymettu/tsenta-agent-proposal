#!/bin/sh
# Worker start (551 s9.4 and source review F3; owner grant 19:01:16: memory-only credential files).
# Stage 1, before any secret exists: /run/secrets, /demo/state, /tmp and /demo/io must all be tmpfs; /run/secrets mode
#   0700 owned by this user; and swap off for this container (cgroup2 memory.swap.max = 0, from equal --memory and
#   --memory-swap, because the daemon rejects tmpfs noswap and the VM has a swap file; 551 C1, C2). Any failure exits.
# Stage 2: wait, bounded, for the operator's vault fill, which streams into model_key.part and then renames it to
#   model_key (atomic on tmpfs, so a half-written key is never read; 551 R1); re-check
#   0600 and owner; generate the gateway token in the same tmpfs; exec the gateway with both in THIS process's env.
set -eu
umask 077
S=/run/secrets
fail() { echo "worker: $1; refusing" >&2; exit 65; }
for m in "$S" /demo/state /tmp /demo/io; do [ "$(findmnt -no FSTYPE "$m" 2>/dev/null)" = tmpfs ] || fail "$m is not tmpfs"; done
[ "$(stat -c %a:%u "$S")" = "700:$(id -u)" ] || fail "$S is not 0700 and owned by $(id -u)"
[ "$(cat /sys/fs/cgroup/memory.swap.max 2>/dev/null)" = 0 ] || fail "swap is possible for this container (memory.swap.max is not 0)"
SWAP="memory.swap.max 0"
mkdir -p "$HOME"   # /demo/state is a fresh tmpfs each start (551 P1), so HOME=/demo/state/home must be created
echo "worker: stage 1 ok (tmpfs 0700, $SWAP); waiting for the key fill" >&2
i=0
while [ ! -s "$S/model_key" ]; do i=$((i + 1)); [ "$i" -le "${KEY_WAIT_SECONDS:-1800}" ] || fail "no key fill within the wait"; sleep 1; done
[ "$(stat -c %a:%u "$S/model_key")" = "600:$(id -u)" ] || fail "model_key is not 0600 and owned by $(id -u)"
if [ "${CANARY:-}" = 1 ]; then echo "worker: canary stage 2 ok (key file 0600 node); not starting the gateway" >&2; exec sleep infinity; fi
cp /opt/demo/openclaw.json5 "$OPENCLAW_CONFIG_PATH"
sha256sum "$OPENCLAW_CONFIG_PATH" | cut -c1-64 > /demo/state/config.sha256   # for the 9.5 restore check (not a secret)
mkdir -p /demo/state/logs
head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$S/gateway_token"
ANTHROPIC_API_KEY="$(cat "$S/model_key")"
OPENCLAW_GATEWAY_TOKEN="$(cat "$S/gateway_token")"
export ANTHROPIC_API_KEY OPENCLAW_GATEWAY_TOKEN
echo "worker: stage 2 ok; starting gateway" >&2
exec openclaw gateway run
