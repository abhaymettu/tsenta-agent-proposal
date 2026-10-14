#!/bin/sh
# The fill sink (551 s9.4 step 3; owner grant 19:01:16). The value arrives on THIS script's stdin and streams straight
# into `docker exec -i` stdin; it is never in argv, env, a host file, a receipt or a log. The value source must itself be
# stdin-clean (openclaw/fill-route.py, or a pipe; never `echo "$KEY"`).
# Inside the container, as the runtime user (node), with umask 077, it refuses unless /run/secrets is tmpfs, mode 700,
# owned by node; swap is off for the container (memory.swap.max 0); and model_key does not exist yet (single use).
# The value goes into this fill's own mktemp file (model_key.part.XXXXXX), checked 600:node, then hard-linked to
# model_key. The link fails if model_key exists, so concurrent fills cannot overwrite each other and the reader only ever
# sees a complete file. A trap removes this fill's part file on any exit (INT and TERM included). Empty input is refused.
# The input must be framed as <value>\nOC551-END\n (fill-route.py adds the frame). A stream that ends early, because the
# docker CLI died or the route's timeout killed it, lacks the end line and is refused (exit 8), so a truncated value is
# never published. The frame is stripped before the link (551 M1).
# Receipt line: time, container, "filled: yes|no (exit N)". Nothing about the value (no hash, no length).
# Usage: <stdin-clean framed value source> | openclaw/fill-key.sh oc551-worker
set -eu
C="${1:?container}"
case "$C" in oc551-worker|oc551-edge) ;; *) echo "fill: only oc551-worker or oc551-edge" >&2; exit 2 ;; esac
R="${TSENTA_AUDIT_DIR:-$PWD/run/audit}/fill-receipts.log"; mkdir -p "${R%/*}"
if docker --context desktop-linux exec -i -u node "$C" sh -c '
    set -eu; umask 077; S=/run/secrets; P=
    trap "[ -n \"\$P\" ] && rm -f \"\$P\"" EXIT
    trap "exit 130" INT TERM
    [ "$(findmnt -no FSTYPE $S)" = tmpfs ] || exit 3
    [ "$(stat -c %a:%U $S)" = "700:node" ] || exit 7
    [ "$(cat /sys/fs/cgroup/memory.swap.max)" = 0 ] || exit 6
    [ ! -e $S/model_key ] || exit 4
    P=$(mktemp $S/model_key.part.XXXXXX)
    cat > "$P"
    n=$(stat -c %s "$P"); [ "$n" -gt 11 ] || exit 5
    [ "$(tail -c 11 "$P")" = "$(printf "\nOC551-END")" ] || exit 8
    truncate -s $((n - 11)) "$P"
    [ -s "$P" ] || exit 5
    [ "$(stat -c %a:%U "$P")" = "600:node" ] || exit 9
    ln "$P" $S/model_key 2>/dev/null || exit 4'; then r=yes; else r="no (exit $?)"; fi
printf '%s %s filled: %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$C" "$r" >> "$R"
echo "filled: $r"
[ "$r" = yes ]
