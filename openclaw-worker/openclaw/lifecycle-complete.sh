#!/bin/sh
# Build-time only, as root, under `RUN --network=none` (551 OPENCLAW-LIFECYCLE-REVIEW.md, supported route). The pin
# ships .openclaw-lifecycle-pending; the package's own first run of openclaw.mjs takes its lifecycle lock, runs its
# preinstall and postinstall, and removes the marker. This runs that once and ENFORCES its effect on all of
# /opt/openclaw (551 L1, L2): a per-entry manifest (sha256 of every file, every symlink target, every directory) taken
# before and after must differ by exactly one removed entry, the marker; 0 added, 0 changed. It also fails if the fs-safe
# native had to be fetched or is unavailable, or a lifecycle artifact remains. It never disables the postinstall and
# never enables the network. Writes the record to /opt/demo/lifecycle-record.txt.
set -eu
export LC_ALL=C
ROOT=/opt/openclaw
PKG=$ROOT/node_modules/openclaw
MARKER=./node_modules/openclaw/.openclaw-lifecycle-pending
O=/opt/demo/lifecycle-record.txt
fail() { echo "lifecycle: FAIL: $1" >&2; exit 1; }
manifest() {
  cd "$ROOT"
  { find . -type f -exec sha256sum {} + | sed 's/^/F /'
    find . -type l -printf 'L %p -> %l\n'
    find . -type d -printf 'D %p\n'; } | sort -k2
}
[ -e "$PKG/.openclaw-lifecycle-pending" ] || fail "marker not present before the run (unexpected tarball state)"
manifest > /tmp/m-before
{
  echo "scope: all of $ROOT; entries before: $(wc -l < /tmp/m-before)"
  echo "dist files $(find "$PKG/dist" -type f | wc -l); inventory entries $(cd "$PKG" && node -e 'const i=require("./dist/postinstall-inventory.json");console.log(Array.isArray(i)?i.length:Object.keys(i).length)')"
} > "$O"
touch /tmp/stamp
cd "$PKG"
if node openclaw.mjs --version > /tmp/lifecycle.log 2>&1; then rc=0; else rc=$?; fi
cat /tmp/lifecycle.log
[ "$rc" -eq 0 ] || fail "openclaw.mjs --version exited $rc"
! grep -q -e 'fs-safe native support is unavailable' -e 'restored @openclaw/fs-safe' /tmp/lifecycle.log || fail "fs-safe native fetched or unavailable"
[ ! -e .openclaw-lifecycle-pending ] || fail "marker still present"
[ ! -e dist/openclaw-install-guard ] || fail "legacy guard present"
[ ! -e .openclaw-lifecycle-lock ] || fail "lifecycle lock left behind"
! ls -d .openclaw-prebuild-* >/dev/null 2>&1 || fail "prebuild staging left behind"
manifest > /tmp/m-after
diff /tmp/m-before /tmp/m-after > /tmp/m-diff || true
removed=$(grep -c '^<' /tmp/m-diff || true); added=$(grep -c '^>' /tmp/m-diff || true)
{
  echo "entries after: $(wc -l < /tmp/m-after); manifest diff: $removed removed, $added added"
  sed -n 's/^< //p' /tmp/m-diff | sed 's/^/  removed: /' | head -20
  sed -n 's/^> //p' /tmp/m-diff | sed 's/^/  added or changed: /' | head -20
  echo "version: $(tail -1 /tmp/lifecycle.log)"
  echo "files newer than the pre-run stamp on / (info only, excl. /proc /sys /tmp):"
  find / -xdev \( -path /proc -o -path /sys -o -path /tmp \) -prune -o -type f -newer /tmp/stamp -print | sed 's/^/  /' | head -50
} >> "$O"
cat "$O"
[ "$removed" -eq 1 ] && [ "$added" -eq 0 ] || fail "manifest diff is not exactly one removed entry ($removed removed, $added added or changed)"
grep -q "^< F [0-9a-f]\{64\}  $MARKER\$" /tmp/m-diff || fail "the one removed entry is not $MARKER"
echo "lifecycle: PASS (exactly the marker removed; 0 added, 0 changed)" | tee -a "$O"
rm -f /tmp/m-before /tmp/m-after /tmp/m-diff /tmp/lifecycle.log /tmp/stamp
