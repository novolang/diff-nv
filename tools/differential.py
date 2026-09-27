#!/usr/bin/env python3
"""Write tests/differential_tests.nv from GNU diffutils and Python's difflib.

Two independent implementations answer questions this package answers,
and the file this script writes holds their answers as vectors:

1. GNU `diff --minimal` finds a shortest edit script.  Every shortest
   script deletes and inserts the same number of lines, so the two
   counts are recorded and this package's unbounded Myers walk must
   answer the same two numbers.
2. GNU `diff -U3` writes a unified diff.  It is recorded as text, and
   this package must parse it and apply it to the left file to produce
   the right one.
3. `difflib.SequenceMatcher`, with its junk heuristic off, matches a
   number of lines.  Its matching is not always a longest one, so this
   package's longest common subsequence must be at least as long.

The pairs are drawn from a small vocabulary of lines, so that lines
repeat and the diffs have more than one shortest answer.  The draws come
from a fixed linear congruential sequence, so the file is the same on
every run.

Run from the package root:  python3 tools/differential.py
The output is passed through `novo fmt`.
"""
import difflib
import os
import subprocess
import tempfile

VOCAB = ['a', 'b', 'c', 'd', 'fn main()', '    x', '    y', '', '}', 'return 0']
COUNT = 60


class Lcg:
    def __init__(self, seed):
        self.state = seed

    def next(self, bound):
        self.state = (self.state * 1103515245 + 12345) % (1 << 31)
        return (self.state >> 8) % bound


def draw_pair(rng):
    n = rng.next(14)
    a = [VOCAB[rng.next(len(VOCAB))] for _ in range(n)]
    b = list(a)
    for _ in range(rng.next(6)):
        op = rng.next(3)
        if op == 0 and b:
            del b[rng.next(len(b))]
        elif op == 1:
            b.insert(rng.next(len(b) + 1), VOCAB[rng.next(len(VOCAB))])
        elif b:
            b[rng.next(len(b))] = VOCAB[rng.next(len(VOCAB))]
    ta = ''.join(x + '\n' for x in a)
    tb = ''.join(x + '\n' for x in b)
    if rng.next(4) == 0 and tb:
        tb = tb[:-1]
    return ta, tb


def gnu(ta, tb):
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, 'a'), os.path.join(d, 'b')
        open(pa, 'w').write(ta)
        open(pb, 'w').write(tb)
        normal = subprocess.run(['diff', '--minimal', pa, pb], capture_output=True, text=True).stdout
        unified = subprocess.run(['diff', '-U3', '--label', 'a', '--label', 'b', pa, pb],
                                 capture_output=True, text=True).stdout
    deleted = sum(1 for line in normal.splitlines() if line.startswith('< '))
    inserted = sum(1 for line in normal.splitlines() if line.startswith('> '))
    return deleted, inserted, unified


def nv(s):
    out = s.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
    return '"' + out.replace('\n', '\\n').replace('\t', '\\t') + '"'


def main():
    rng = Lcg(20260927)
    rows = []
    for _ in range(COUNT):
        ta, tb = draw_pair(rng)
        deleted, inserted, unified = gnu(ta, tb)
        sm = difflib.SequenceMatcher(None, ta.splitlines(True), tb.splitlines(True), autojunk=False)
        matched = sum(m.size for m in sm.get_matching_blocks())
        rows.append((ta, tb, deleted, inserted, matched, unified))

    lines = []
    lines.append('// differential_tests.nv — this package against GNU diffutils and')
    lines.append("// Python's difflib, which answer the same questions independently.")
    lines.append('//')
    lines.append('// Written by tools/differential.py; do not edit by hand.  Each vector')
    lines.append('// is two texts, the line counts GNU `diff --minimal` deletes and')
    lines.append('// inserts, the number of lines difflib matches, and the unified diff')
    lines.append('// GNU `diff -U3` writes.  See the script for what each is compared')
    lines.append('// with.')
    lines.append('')
    lines.append('use std.test')
    lines.append('use std.list')
    lines.append('use diffunit')
    lines.append('use diffscript')
    lines.append('use diffrender')
    lines.append('use diffpatch')
    lines.append('')
    lines.append('struct Vector')
    lines.append('    a: Str')
    lines.append('    b: Str')
    lines.append('    deleted: Int')
    lines.append('    inserted: Int')
    lines.append('    difflib_matched: Int')
    lines.append('    gnu_unified: Str')
    lines.append('')
    lines.append('fn vectors() -> [Vector]')
    lines.append('    [')
    for i, (ta, tb, d, ins, m, u) in enumerate(rows):
        sep = ',' if i + 1 < len(rows) else ''
        lines.append('        Vector { a: %s, b: %s,' % (nv(ta), nv(tb)))
        lines.append('                 deleted: %d, inserted: %d, difflib_matched: %d,' % (d, ins, m))
        lines.append('                 gnu_unified: %s }%s' % (nv(u), sep))
    lines.append('    ]')
    lines.append('')
    lines.append('// The text a unified diff produces when applied to `a`.')
    lines.append('fn applied(a: Str, patch: Str) -> Str')
    lines.append('    if patch == ""')
    lines.append('        return a')
    lines.append('    match diffpatch.parse_unified(patch)')
    lines.append('        Err(_) => "<parse error>"')
    lines.append('        Ok(p)  =>')
    lines.append('            let files = p.files')
    lines.append('            diffpatch.apply(a, files[0], diffpatch.strict_apply_options()).text')
    lines.append('')
    lines.append('// The text a unified diff produces when applied backwards to `b`.')
    lines.append('fn unapplied(b: Str, patch: Str) -> Str')
    lines.append('    if patch == ""')
    lines.append('        return b')
    lines.append('    let o = DiffApplyOptions { fuzz: 0, max_offset: 0, reverse: true,')
    lines.append('                               ignore_whitespace: false, detect_already_applied: false }')
    lines.append('    match diffpatch.parse_unified(patch)')
    lines.append('        Err(_) => "<parse error>"')
    lines.append('        Ok(p)  =>')
    lines.append('            let files = p.files')
    lines.append('            diffpatch.apply(b, files[0], o).text')
    lines.append('')
    lines.append('@test')
    lines.append('fn test_the_shortest_script_has_gnu_diffs_counts() [io]')
    lines.append('    for v in vectors()')
    lines.append('        let input = diffunit.tokenize(v.a, v.b, DiffLines)')
    lines.append('        let c = diffscript.counts(diffscript.diff(input, diffscript.minimal_options()))')
    lines.append('        test.assert(c.0 == v.deleted)')
    lines.append('        test.assert(c.1 == v.inserted)')
    lines.append('')
    lines.append('@test')
    lines.append('fn test_the_common_subsequence_is_at_least_as_long_as_difflibs() [io]')
    lines.append('    for v in vectors()')
    lines.append('        let input = diffunit.tokenize(v.a, v.b, DiffLines)')
    lines.append('        let pairs = diffscript.common_subsequence(input.a.ids, input.b.ids,')
    lines.append('                                                  diffscript.minimal_options())')
    lines.append('        test.assert(list.len(pairs) >= v.difflib_matched)')
    lines.append('')
    lines.append('@test')
    lines.append('fn test_gnu_diffs_unified_output_parses_and_applies() [io]')
    lines.append('    for v in vectors()')
    lines.append('        test.assert(applied(v.a, v.gnu_unified) == v.b)')
    lines.append('')
    lines.append('@test')
    lines.append('fn test_every_walks_own_unified_output_applies_both_ways() [io]')
    lines.append('    let walks = [diffscript.minimal_options(), diffscript.patience_options(),')
    lines.append('                 diffscript.histogram_options()]')
    lines.append('    for v in vectors()')
    lines.append('        let input = diffunit.tokenize(v.a, v.b, DiffLines)')
    lines.append('        for o in walks')
    lines.append('            let s = diffscript.diff(input, o)')
    lines.append('            let text = diffrender.unified(input, s, diffrender.unified_options_named(3, "a", "b"))')
    lines.append('            test.assert(applied(v.a, text) == v.b)')
    lines.append('            test.assert(unapplied(v.b, text) == v.a)')
    lines.append('')
    open('tests/differential_tests.nv', 'w').write('\n'.join(lines) + '\n')
    subprocess.run(['novo', 'fmt', 'tests/differential_tests.nv'], check=False)


if __name__ == '__main__':
    main()
