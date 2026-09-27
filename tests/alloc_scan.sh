#!/usr/bin/env bash
# tests/alloc_scan.sh — nothing in `tzrule` allocates, as a check that
# can fail.
#
# `tzrule` is the half a device runs.  What makes it usable there is
# that it puts nothing on the heap.  The emitted LLVM is where that is
# true or false, so this reads it.
#
# There are three runs, because a check that cannot fail is not a check.
#
#   1. Every function in `tzrule` appears in the IR of
#      `tests/alloc_probe.nv` at `--opt=0`, and none of them calls the
#      allocator, directly or through a runtime entry point that
#      allocates on the caller's behalf.
#   2. The scan still sees an allocation.  A heap list literal is
#      spliced into `offset_for` on a copy of the tree, with the
#      module's `@tier(embedded)` annotations taken off so the compiler
#      is not what refuses it, and the scan has to name it.
#   3. The compiler still refuses the same splice with
#      `@tier(embedded)` left on.  An annotation that stopped being
#      enforced looks exactly like one that passes.
#
# Run from anywhere:  bash tests/alloc_scan.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$(cd "$HERE/.." && pwd)"
NOVO="${NOVO:-$HOME/.novo/bin/novo}"
SCAN="$HERE/alloc_scan.py"

PASS=0; FAIL=0
pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1"; [ -n "${2:-}" ] && echo "$2" | sed 's/^/      /'; FAIL=$((FAIL + 1)); }

echo ""
echo "══════════════════════════════════════════"
echo "  tz-nv — nothing in tzrule allocates"
echo "══════════════════════════════════════════"

[ -x "$NOVO" ] || { fail "novo present at $NOVO"; echo "pass=$PASS fail=$FAIL"; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/tz-nv-alloc.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# The splice is a heap list literal bound in `offset_for`, and read, so
# it cannot be folded away.  The second argument says whether the module
# keeps its `@tier(embedded)` lines.
splice() {  # splice <src/tzrule.nv> <keep-tier: yes|no>
  python3 - "$1" "$2" <<'PY'
import sys
path, keep_tier = sys.argv[1], sys.argv[2]
s = open(path).read()
anchor = ("fn offset_for(std_offset_seconds: Int, dst_offset_seconds: Int, is_dst: Bool) -> Int []\n"
          "    if is_dst")
if anchor not in s:
    sys.exit("anchor not found — alloc_scan.sh's splice is measuring nothing")
new = ("fn offset_for(std_offset_seconds: Int, dst_offset_seconds: Int, is_dst: Bool) -> Int []\n"
       "    let probe = [1, 2, 3]\n"
       "    if probe[0] > 99\n"
       "        return 0\n"
       "    if is_dst")
s = s.replace(anchor, new)
if keep_tier == "no":
    # Every function of the module carries the annotation, and an
    # annotated function may not call an unannotated one, so it comes
    # off the whole module.  What is left is a module the compiler no
    # longer constrains, which is the state in which the emitted IR is
    # the only thing that can catch the allocation.
    s = s.replace("@tier(embedded)\n", "")
open(path, 'w').write(s)
PY
}

build_probe() {  # build_probe <tree>
  ( cd "$1" && NOVO_LEAK_CHECK=0 timeout 900 "$NOVO" build --opt=0 \
      -o "$1/probe.bin" tests/alloc_probe.nv ) >"$1/build.log" 2>&1
}

# ── 1. nothing in the core allocates ─────────────────────────────────

cp -r "$PKG" "$WORK/ok" 2>/dev/null
rm -rf "$WORK/ok/_novo"
if build_probe "$WORK/ok"; then
  IR="$WORK/ok/_novo/alloc_probe.ll"
  if [ -s "$IR" ]; then
    report="$(python3 "$SCAN" "$IR")"
    if [ "${report#OK}" != "$report" ]; then
      pass "nothing in tzrule allocates — ${report#OK }"
    else
      fail "nothing in tzrule allocates" "${report#FAIL }"
    fi
  else
    fail "nothing in tzrule allocates" "no _novo/alloc_probe.ll emitted"
  fi
else
  fail "the allocation probe builds" "$(grep -E 'error' "$WORK/ok/build.log" | head -5)"
fi

# ── 2. the scan still sees an allocation ─────────────────────────────

cp -r "$PKG" "$WORK/neg" 2>/dev/null
rm -rf "$WORK/neg/_novo"
if splice "$WORK/neg/src/tzrule.nv" no >"$WORK/splice.log" 2>&1 \
   && build_probe "$WORK/neg"; then
  neg="$(python3 "$SCAN" "$WORK/neg/_novo/alloc_probe.ll")"
  if [ "${neg#FAIL}" != "$neg" ] && printf '%s' "$neg" | grep -q 'offset_for'; then
    pass "the scan still sees an allocation spliced into tzrule"
  else
    fail "the scan still sees an allocation spliced into tzrule" \
         "expected a finding naming offset_for; got: $neg"
  fi
else
  fail "the negative control builds" \
       "$(cat "$WORK/splice.log"; grep -E 'error' "$WORK/neg/build.log" | head -5)"
fi

# ── 3. the compiler still refuses the splice ─────────────────────────

cp -r "$PKG" "$WORK/tier" 2>/dev/null
rm -rf "$WORK/tier/_novo"
splice "$WORK/tier/src/tzrule.nv" yes >"$WORK/tsplice.log" 2>&1
if build_probe "$WORK/tier"; then
  fail "@tier(embedded) still refuses a heap list literal" \
       "the build succeeded with a list literal in an @tier(embedded) function"
else
  pass "@tier(embedded) still refuses a heap list literal in tzrule"
fi

echo ""
echo "pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
