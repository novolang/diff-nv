# Changelog

All notable changes to diff-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-09-27

The first implementation of the interface published as 0.0.1: the
three walks, unified and side-by-side rendering, patch parsing and
application, and the three-way merge.

### Changed, breaking

- `DiffDelete` and `DiffInsert` carry both ranges, `DiffDelete(a, b)`
  and `DiffInsert(a, b)`, with the other side's range empty at the
  position of the change.  With one range, an insertion had no position
  on the left, and `op_a` could not answer one.
- `DiffTokens` gains `unit` and `policy`, the rule its ids were made
  under.  `intern_pair` needs them to number two separately tokenised
  inputs, and `token_unterminated` reads the unit.
- `DiffFilePatch` gains `source`, the patch text its spans point into,
  so `apply` can read a hunk's lines from the file patch alone.
- `diffrender.inline_marks` takes the granularity the refinement was
  made at, because a refined script's ranges are token indices of that
  granularity.
- Every function that appends to a caller's buffer takes it as a `var`
  parameter: `unified_into`, `hunk_header_into`, `side_by_side_into`,
  `stat_line_into`, `apply_into`, `reject_file_into`, `merge3_into` and
  `conflict_into`.  Under the toolchain's list rule a plain parameter
  cannot be written.
- `DiffTokenPolicy.ignore_blank_lines` makes every whitespace-only line
  one token.  A run of blank lines matches a run of the same length and
  not of any length, because an equal operation covers the same number
  of tokens on both sides.

### Behaviour the interface left open

- A bounded Myers walk that reaches `max_steps` finishes with the
  histogram walk.  Patience and histogram use Myers on a region with no
  anchor.
- `unified_options` writes no `---` and `+++` lines when both names are
  empty; a script with no change renders nothing.
- `DiffPatchTruncated` is a hunk header with no body before the end of
  the text; a body cut short is `DiffPatchHunkCountMismatch`.
- `apply` looks for each hunk at its header's line, moved by the lines
  earlier hunks added or removed and by the offset the previous hunk
  was found at.  Two matches at the same distance are
  `DiffRejectAmbiguous`.
- `merge3` writes unchanged regions from `ours`.  A conflict's markers
  always start on a fresh line.
- The interface's test of `ratio` expected 0.8 for `qabxcd` against
  `abycdf`; `difflib` answers 8/12, and the test now does too.

## 0.0.2 — 2026-09-15

README rewritten to the package README style guide (docs/writing-a-readme.md); no change to the interface.

## 0.0.1 — 2026-09-11

The **interface**: every signature and every effect row, and no bodies.
`stability = "draft"`, and the release is recorded `implemented = false`.

### Added

- `diffunit` — the three granularities (`DiffLines`, `DiffWords`,
  `DiffGraphemes`), the tokenisation that interns two inputs against
  each other, `DiffTokenPolicy` as the equivalence written down, and
  the two interval types that the compiler keeps apart.
- `diffscript` — `DiffOp` and `DiffScript`, with Myers, patience and
  histogram as named walks, a step bound rather than a time bound, and
  `diff_ids` as the public integer entry point.
- `diffrender` — `unified_into` / `unified` / `unified_to`, the row
  list an editor paints itself, side-by-side layout over a
  caller-supplied width function, and `hunk_header_into` alone.
- `diffpatch` — a unified diff parsed to spans into its own text, and
  applied with an offset and a fuzz that are two separate knobs.
- `diffmerge` — a three-way merge whose conflicts are values with
  ranges into all three inputs, git's three marker styles, and
  `marker_size` for the file that contains marker lines of its own.

### Known

- **`DiffOp` is the load-bearing interface**, and it carries token
  ranges and no text. The algorithm never sees a string; the
  granularity is a tokeniser rather than a code path; a policy changes
  the ids and never the spans.
- **`DiffScript.minimal` says whether the answer is minimal**, because
  a bounded Myers walk that degrades silently makes a caller unable to
  ask. The bound is steps and not milliseconds: a `core` package has no
  clock, and a reproducible diff is worth more than a responsive one.
- **`apply` does not answer a `Result`.** A partial application has
  produced a file and a reject list, and an `Err` would throw the file
  away.
- **`merge3` answers conflicts as values.** Parsing marker text back is
  wrong for the file that contains marker text, which is the file that
  needed the option in the first place.
- **`@tier(embedded)` is not claimed**, and the README says why: the
  token tables, the op list and the Myers path array all scale with the
  input, and a device variant would be a different surface rather than
  an annotation on this one.
- **One dependency**, `unicode-nv`, for the two UAX #29 granularities.
- The scaffold's `src/diff.nv` was renamed: `diff` is a module name a
  consumer's own tree is likely to want, and module names collide on
  the same terms as type names.

### Design notes

The consumers the surface was designed against. novim has no diff and
two places want one: its LSP client sends `textDocument/didChange` with
the whole document on every debounced keystroke, where the protocol's
incremental form wants ranges with replacement text, which is
`diffrender.lines` over a `DiffLines` script; and it has no `:diff`
command and no gutter marks, which is the same row list painted with
novim's own attributes. snapshot-nv is planned as snapshot assertions
over this package and needs `diffscript.unchanged` and
`diffrender.unified`. `novo fmt --check` needs the same two over a
`minimal_options()` script.

The module names. The scaffold's `src/diff.nv` was renamed before the
first build: module names collide across a whole assembly on the same
terms as type names, and `diff` is a name a consumer's own tree is
likely to want. Hence `diffunit`, `diffscript`, `diffrender`,
`diffpatch` and `diffmerge`.
