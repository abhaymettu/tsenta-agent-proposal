#!/bin/sh
# One agent turn, invoked by the host core as a fixed command:
#   docker --context desktop-linux exec oc551-worker /opt/demo/agent-turn.sh <session-key>
# The task text is read from /demo/io/task.md (written by the core); model output never becomes an argument here.
set -eu
case "$1" in tsenta-demo-g[0-9]*-P[0-9][0-9]) ;; *) echo '{"ok":false,"error":{"message":"bad session key"}}'; exit 2 ;; esac
OPENCLAW_GATEWAY_TOKEN="$(cat /run/secrets/gateway_token)"
export OPENCLAW_GATEWAY_TOKEN
exec openclaw agent --agent main --session-key "$1" --message-file /demo/io/task.md --json --timeout 600
