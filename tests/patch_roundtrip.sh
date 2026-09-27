#!/usr/bin/env bash
# tests/patch_roundtrip.sh — this package's unified diffs, applied by GNU
# patch.
#
# A unified diff is an interchange format, so the check that matters is
# whether another program reads it back.  For the same pairs of texts
# tools/differential.py draws, this builds tests/roundtrip_probe.nv,
# writes each pair's diff with each of the three walks, applies it with
# `patch` to the left text, and compares the result with the right text
# byte for byte.  It also counts how many of the Myers diffs are the
# same bytes as `diff -U3` writes, which is reported and not asserted:
# two shortest scripts can place a change differently.
#
# Run from anywhere:  bash tests/patch_roundtrip.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(cd "$HERE/.." && pwd)"
NOVO="${NOVO:-$HOME/.novo/bin/novo}"
command -v patch >/dev/null || { echo "  ✗ GNU patch is not installed"; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/diff-nv-roundtrip.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# The probe is built as a module of a copy of the package, so it resolves
# the package's modules and its dependency.
cp -r "$PKG" "$WORK/pkg"
rm -rf "$WORK/pkg/_novo"
cp "$PKG/tests/roundtrip_probe.nv" "$WORK/pkg/src/roundtrip_probe.nv"
printf '\n[[bin]]\nname = "roundtrip-probe"\npath = "src/roundtrip_probe.nv"\n' >>"$WORK/pkg/novo.toml"
( cd "$WORK/pkg" && NOVO_LEAK_CHECK=0 timeout 900 "$NOVO" pkg build --bin roundtrip-probe ) \
    >"$WORK/build.log" 2>&1 || { echo "  ✗ the probe builds"; tail -5 "$WORK/build.log"; exit 1; }

python3 - "$PKG" "$WORK" <<'PY'
import os, subprocess, sys
pkg, work = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(pkg, 'tools'))
import differential as d

rng = d.Lcg(20260927)
fails = same = total = 0
for i in range(d.COUNT):
    ta, tb = d.draw_pair(rng)
    pa, pb = os.path.join(work, 'a'), os.path.join(work, 'b')
    open(pa, 'w').write(ta)
    open(pb, 'w').write(tb)
    gnu = subprocess.run(['diff', '-U3', '--label', 'a', '--label', 'b', pa, pb],
                         capture_output=True, text=True).stdout
    for walk in ('myers', 'patience', 'histogram'):
        ours = subprocess.run([os.path.join(work, 'pkg', 'roundtrip-probe'), pa, pb, walk],
                              capture_output=True, text=True).stdout
        total += 1
        if walk == 'myers' and ours == gnu:
            same += 1
        out = os.path.join(work, 'out')
        if ours == '':
            got = ta
        else:
            r = subprocess.run(['patch', '-s', '-o', out, pa], input=ours,
                               capture_output=True, text=True)
            got = open(out).read() if r.returncode == 0 else None
        if got != tb:
            fails += 1
            print('  ✗ pair %d, %s: patch did not reproduce the right text' % (i, walk))
print('  %d of %d diffs applied by GNU patch; %d of %d Myers diffs are diff -U3\'s bytes'
      % (total - fails, total, same, d.COUNT))
sys.exit(1 if fails else 0)
PY
