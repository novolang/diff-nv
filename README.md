# diff-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`. Installing this package works;
calling it panics with `not implemented`.

## What this is

Text diffing, sans-IO: two strings in, an edit script out, and four
things that read one — a unified diff, a side-by-side diff, a patch
applied with fuzz, and a three-way merge.

- `diffunit` — the three granularities, the tokens they cut the inputs
  into, and the two kinds of interval that are never the same thing;
- `diffscript` — `DiffOp`, and the Myers, patience and histogram walks
  that produce a list of them;
- `diffrender` — unified, side by side, and the row list an editor
  paints itself;
- `diffpatch` — a unified diff parsed back in, and applied;
- `diffmerge` — three inputs, one output, and the conflicts as values.

```
novo pkg add diff-nv
novo pkg build
novo test
```

## The one example that will work

```novo ignore
use diffunit
use diffscript
use diffrender

// Two files, and the unified diff between them.
fn show(a: Str, b: Str) -> Str
    let input = diffunit.tokenize(a, b, DiffLines)
    let script = diffscript.diff(input, diffscript.default_options())
    diffrender.unified(input, script, diffrender.unified_options(3))
```

## The load-bearing interface: `DiffOp`

```novo ignore
pub enum DiffOp
    DiffEqual(a: DiffRange, b: DiffRange)
    DiffDelete(a: DiffRange)
    DiffInsert(b: DiffRange)
    DiffReplace(a: DiffRange, b: DiffRange)
```

Four variants carrying **token ranges and no text**. Everything else
in this package is a reader of that list, and so is every consumer:
snapshot-nv asks whether a script is empty, `novo fmt --check` asks the
same, novim paints one, `diffpatch` turns a patch off disk into one and
back.

Three things follow from the ranges being token indices rather than
bytes, and they are why the design holds:

**The algorithm never sees text.** `diffscript.diff_ids([Int], [Int])`
is the whole walk. `diffunit` is what turns two strings into two id
lists, so lines, words and grapheme clusters are one algorithm rather
than three code paths — and a caller with tokens of its own (a
snapshot library over records, a harness over syntax trees) interns
them itself and never touches `diffunit`.

**The equivalence is separable from the bytes.**
`DiffTokenPolicy` decides which tokens get the same **id**, and
touches nothing else. `git diff -w` and `git diff` differ here by one
boolean, and both render the caller's original bytes — because the
spans were never folded. A tokeniser that lower-cased its output would
render a lower-cased file.

**Two intervals, two types.** `DiffSpan` is bytes into a `Str`;
`DiffRange` is token indices into a `DiffTokens`. Confusing them is the
classic diff defect — a `@@` header printed with byte offsets, a slice
taken with a line number — and here the compiler refuses the
confusion. `diffunit.range_span` is the only bridge.

## The second decision worth arguing: `DiffScript` says whether it is minimal

Myers' O(ND) is quadratic in the worst case, so every real
implementation bounds the search and answers a coarse script when the
bound is hit — `similar` calls it a deadline, git calls it
`--no-minimal`. A caller showing a person a diff does not care. A
caller asserting two files are identical, or applying the script as a
patch, very much does, and an API that hides the degradation makes that
caller unable to ask. So `DiffScript` carries `minimal`, and the bound
is counted in **steps rather than milliseconds**: a `core` package has
no clock, and a step bound is reproducible where a time bound is not —
the same two files must produce the same diff on every machine, or a
snapshot test is a coin toss.

## Two `Result`s this package deliberately does not answer

`diffpatch.apply` **does not answer a `Result`.** A patch of five
hunks that places three and rejects two has produced a file and a
reject list. That is what `patch(1)` does, it is what a person running
it expects, and it is the only answer a caller can act on: an `Err`
throws away the three hunks that went in, and the caller then
re-implements partial application to get them back. `DiffApplyResult`
carries the text, what each placed hunk cost, and the rejects;
`rejects_empty` is the one-line check for a caller who wanted
all-or-nothing after all. Parsing a patch *is* a `Result`, and the
asymmetry is the point: a malformed patch is a bug in the bytes and
there is nothing to hand back.

`diffmerge.merge3` **answers its conflicts as values**, not only as
marker text. A merge that produced only text with `<<<<<<<` in it makes
every consumer parse its own output back — and that reparse is wrong
exactly when it matters, on a file whose own content contains a marker
line, which is every file that documents merge conflicts, this one
included. `conflicts_only` is the same question with nothing rendered.

## The layer, and why

`core`. A diff is arithmetic over two strings the caller already
holds: nothing is read, nothing is written, no clock is consulted, and
no text is copied out of either input until a renderer is asked for
bytes.

The one place a stream could have entered is writing a rendered diff
out, and that is the effect-polymorphic shape:

```novo ignore
pub fn unified_to<W: Write[e]>(w: W, input: DiffInput, s: DiffScript,
                               o: DiffUnifiedOptions) -> ?IoError [e]
```

The clause is `[e]`, bound by the caller's `Write` impl, so a terminal
costs `[io]`, a file costs `[fs]` and an in-memory buffer costs
nothing — and this package has spent none of them. `docs/publishing.md`
§ How a `core` package takes a stream from its host is the rule; this
is the sink half of it. `*_into(out: [u8], …) -> [u8]` is the shape for
a caller that already has a buffer, and `unified(…) -> Str` for one
that wants the string.

## `@tier(embedded)` is not claimed

Deliberately, and the reason is in the shape rather than in effort. An
edit script is a list of operations whose length is the size of the
difference, the token tables are two lists per input, and the Myers
walk holds a furthest-reaching path array that is `O(N + M)` — every
one of them a heap allocation whose size is the input's. A device that
wanted to diff two configuration blobs would need a fixed-capacity
variant with a different surface, not this one with a tier annotation
on it, and pretending otherwise would produce a claim the probe could
only keep by never allocating in a package whose whole job is to build
lists. The honest form is the absence of the claim.

## The reference implementation

The API shape is the `similar` crate's: `DiffOp` with its four
variants, `Algorithm` as an enum, the inline refinement as a separate
call, and the three-way merge beside the two-way diff. Python's
`difflib` supplies `ratio` and its opcode vocabulary, and its
`test_difflib` cases are vectors in `tests/diffscript_tests.nv`.

The rendering is GNU diffutils', byte for byte — a unified diff is an
interchange format that `patch(1)` and `git apply` both read, so the
header tests compare against what `diff -u` writes and not against what
looks reasonable. GNU patch's testsuite supplies the fuzz and offset
cases; `git apply`'s `t4xxx` tests supply the strict ones, and the two
disagree on purpose, which is why both are named option sets. The
merge cases are git's `t6xxx` and `diff3`'s own.

The algorithms are Myers 1986 (§ 4's examples are in the suite), Bram
Cohen's patience diff, and JGit's histogram diff — whose chain limit of
64 this package carries as `DiffOptions.max_chain`.

## Dependencies

`unicode-nv ^0.0.1`, for one granularity and one rule.
`DiffGraphemes` cuts at UAX #29 cluster boundaries, so a combining
accent and a family emoji are each one token and a character diff never
hands a renderer bytes that do not print. `DiffWords` cuts at UAX #29
word boundaries, so a word diff of Japanese or of `foo_bar-baz` splits
where a reader would. `diffunit.word_segments` answers unicode-nv's own
`UniWord` values, which is the honest way for a signature to say "these
are the standard's boundaries and not a guess at them".

Nothing else. The algorithms are over `[Int]` and never look at text at
all.

## The consumers, and what adopting this would take

**novim** (`orbit/novim`) has no diff at all, and two places want one.

Its LSP client sends `textDocument/didChange` with the **whole document
text** on every debounced keystroke — `lsp.lsp_didchange(uri, ver,
text)` in `src/lsp.nv`, called from four sites in `src/main.nv`, each
of which has just recomputed `buf_text(ed)` for the purpose. The
protocol's incremental form wants a list of ranges with replacement
text, which is `diffrender.lines` over a `DiffLines` script between the
previous sent text and the current buffer. Its own comment says the
full-document send "froze the editor on large files"; this is the
missing piece, not a rewrite.

There is also no `:diff` command and no gutter marks. `diffrender.lines`
is the shape for both: rows with a kind, two line numbers and a byte
span, which novim paints with its own attributes. A byte renderer
would not do — a context line beginning with `-` painted as a deletion
is the defect that forces the row list to exist, and
`tests/diffrender_tests.nv` asserts exactly that case.

**snapshot-nv** (a planned `host` row, `testing`/P1) is named in the
plan as "snapshot assertions over diff-nv", and the two calls it needs
are `diffscript.unchanged` — which is deliberately a function rather
than "is the op list empty", because two identical files produce one
`DiffEqual` and not zero ops — and `diffrender.unified`, for the report
it prints when a snapshot moved.

**`novo fmt --check`** wants the same two: the check is
`diffscript.unchanged` on a `minimal_options()` script between the file
and its formatting, and the message is a unified diff. A formatter's
diff is small by construction, so the unbounded walk is the right
option set there.

**novoterm** and **novomux** have no use for this and are not
consumers; they are named here only so the absence is on the record.

## What a row wanted to widen

Nothing. Every function in this package is `[]` except the two
effect-polymorphic writers, whose rows are their callers'.

The one thing that had to change from the plan's row is the **name of
the module**: `novim` already ships `src/fuzzy.nv`, and by the same
rule this package could not ship `diff.nv` — `docs/publishing.md`
§ Public type names are globally unique makes module names collide on
the same terms as type names, and `diff` is a name a consumer's own
module is likely to want. So the modules are `diffunit`, `diffscript`,
`diffrender`, `diffpatch` and `diffmerge`, and `novo pkg init
--interface`'s scaffolded `src/diff.nv` was renamed before the first
build.

## The surface

| module | `pub fn` | `pub struct` | `pub enum` |
| --- | --- | --- | --- |
| `diffunit` | 18 | 5 | 1 |
| `diffscript` | 16 | 3 | 2 |
| `diffrender` | 12 | 4 | 1 |
| `diffpatch` | 12 | 8 | 3 |
| `diffmerge` | 10 | 4 | 2 |
| **total** | **68** | **24** | **9** (33 variants) |
