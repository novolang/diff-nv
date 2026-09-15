# diff-nv

A diff is the shortest description of how one text differs from
another. The classic algorithm for computing one is Eugene Myers'
["An O(ND) Difference Algorithm and Its Variations"](https://neil.fraser.name/writing/diff/myers.pdf)
(1986), and the classic way of writing the answer down is the unified
format that `diff -u` and `patch(1)` exchange, described in the
[GNU diffutils manual](https://www.gnu.org/software/diffutils/manual/html_node/Unified-Format.html).
This package implements both, together with patience and histogram
diffs, patch application and a three-way merge. It is built on
[unicode-nv](https://novo-lang.org/packages/unicode-nv) for its word
and character granularities.

**Status: NOT IMPLEMENTED — interface only.** Every function is declared
with its full signature, but every body is a `todo()` that panics when
called. The package is published so its design can be reviewed and
depended on before it is implemented. Version 0.1.0 will be the first
working release.

## What it is

A **token** is the unit a diff compares. Whole lines is the usual
choice. Words and single characters are the other two, and they are
what an inline highlight inside a changed line is made of. Tokenising
two texts also **interns** them: every distinct token is given a
number, so the algorithm compares integers and never looks at text.

An **edit script** is the answer. It is a list of operations, each of
which says that a run of tokens is equal in both texts, deleted from
the first, inserted into the second, or replaced. The operations carry
token numbers rather than text, so nothing is copied until something
asks for bytes.

A **hunk** is a group of neighbouring operations with some unchanged
context around it. A **unified diff** is a list of hunks written as
text: a header naming both files, then for each hunk a line beginning
`@@` that gives the starting line and the line count on each side, then
the lines themselves prefixed with a space, a minus or a plus.

**Applying** a patch means placing its hunks back into a file. A hunk
rarely lands exactly where its header says, because the file has moved
on. An **offset** is how far from the stated position the hunk was
found. **Fuzz** is how many context lines the matcher is allowed to
ignore in order to find it. A hunk that cannot be placed is a
**reject**.

A **three-way merge** takes a common ancestor and two descendants of
it, and produces one text. Where both sides changed the same region it
produces a **conflict**, which is conventionally written into the
output between `<<<<<<<`, `=======` and `>>>>>>>` marker lines.

The **granularity**, the **equivalence** and the **algorithm** are
three separate choices here. The granularity decides what a token is.
The equivalence decides which tokens share a number, which is how
`diff -w` ignores whitespace. The algorithm decides how the two number
lists are matched.

## Install

```
novo pkg add diff-nv
```

## Example

```novo
use diffunit
use diffscript
use diffrender

fn main() [io]
    let a = "one\ntwo\nthree\n"
    let b = "one\n2\nthree\n"

    // Cut both inputs into line tokens and number them against each
    // other, so the walk compares integers rather than text.
    let input = diffunit.tokenize(a, b, DiffLines)

    // Walk the two token lists and answer the edit script.
    let script = diffscript.diff(input, diffscript.default_options())

    // Render the script as a unified diff with three context lines.
    println(diffrender.unified(input, script, diffrender.unified_options(3)))
```

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a
`not implemented: diff-nv.<module>.<fn>` panic. The tests are the
specification the implementation will have to satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `diffunit` | The three granularities, the tokenisation that numbers two inputs against each other, the equivalence policy, and the two interval types. |
| `diffscript` | The edit script and its operations, and the Myers, patience and histogram walks that produce one. |
| `diffrender` | Unified output, side-by-side output, and the row list an editor paints with its own attributes. |
| `diffpatch` | A unified diff parsed back into hunks, and applied to a text with an offset and a fuzz. |
| `diffmerge` | A three-way merge, with its conflicts as values and as marker text. |

## How to choose an entry point

**`diffunit.tokenize` then `diffscript.diff` is the ordinary path.**
Two strings and a granularity in, an edit script out. Use
`tokenize_with` when you want a non-default equivalence.

**`diffscript.diff_ids` takes two lists of integers.** A caller that
already has tokens of its own, such as a snapshot library over records
or a harness over syntax trees, numbers them itself and never calls
`diffunit` at all.

**`diffrender.unified` returns a string, `unified_into` appends to your
buffer, and `unified_to` writes to a writer you supply.** The third
costs whatever the writer costs and nothing of this package's own. A
terminal costs `[io]`, a file costs `[fs]`, and an in-memory buffer
costs nothing.

**`diffrender.lines` answers rows rather than text.** Each row carries
a kind, a line number on each side and a byte span. An editor painting
a gutter or a `:diff` view wants this, because a context line that
begins with a minus sign is not a deletion and text output cannot tell
the two apart.

**`diffscript.unchanged` is the question a check command asks.** It is
a function rather than a test for an empty operation list, because two
identical texts produce one equal operation and not zero operations.

**`diffpatch.parse_unified` answers a `Result`; `diffpatch.apply` does
not.** See rule 7.

**`diffmerge.merge3` produces text and conflicts; `conflicts_only`
produces the conflicts alone.** Use the second when you want to know
whether a merge is clean without rendering anything.

## The rules a user needs

1. **A `DiffSpan` is bytes and a `DiffRange` is token numbers.** They
   are separate types and the compiler keeps them apart. Printing an
   `@@` header from byte offsets, or slicing a string with a line
   number, is the classic defect this prevents.
   `diffunit.range_span` is the only conversion.
2. **An edit script carries no text.** Every operation holds token
   ranges into the `DiffInput` it came from. Rendering needs both the
   script and the input.
3. **A token policy changes the numbers and never the spans.**
   `ignore_space_policy` gives two tokens that differ only in
   whitespace the same number, which is what `diff -w` does. The
   renderer still emits the caller's original bytes.
4. **Check `DiffScript.minimal` before relying on a script being the
   smallest one.** Myers' algorithm is quadratic in the worst case, so
   the walk is bounded and answers a coarser script when the bound is
   hit. A caller displaying a diff to a person does not care. A caller
   asserting two texts are identical, or turning the script into a
   patch, does.
5. **The bound is counted in steps, not in time.**
   `DiffOptions.max_steps` is that count, and `DiffScript.steps`
   reports what was used. The same two inputs therefore produce the
   same diff on every machine, which a time bound could not promise.
   `minimal_options()` removes the bound.
6. **`DiffOptions.max_chain` is the histogram algorithm's limit.** JGit
   sets it to 64: a token that occurs more often than that is not used
   as an anchor. Patience and Myers ignore the field.
7. **`diffpatch.apply` does not answer a `Result`, and
   `parse_unified` does.** A patch of five hunks that places three and
   rejects two has produced a file and a reject list, which is what
   `patch(1)` does and the only answer a caller can act on.
   `DiffApplyResult` carries the text, what each placed hunk cost, and
   the rejects. `rejects_empty` is the check for a caller who wanted
   all or nothing. A malformed patch, by contrast, has nothing to hand
   back, so parsing is a `Result`.
8. **Offset and fuzz are two separate allowances.**
   `DiffApplyOptions.max_offset` is how far from the stated line a hunk
   may be found. `fuzz` is how many context lines the matcher may
   ignore. GNU patch's default fuzz is 2 and `git apply` uses none,
   which is why `apply_options()` and `strict_apply_options()` are both
   published.
9. **`diffmerge.merge3` answers conflicts as values as well as
   markers.** A consumer that parsed marker text back out of the merged
   output would be wrong on exactly the files that matter, namely the
   ones whose own content contains marker lines.
10. **`DiffMergeOptions.marker_size` exists for those files.** Seven
    characters is git's default. A file that documents merge conflicts
    needs longer markers so its own text is not mistaken for one.
    `has_marker_lines` reports whether an input already contains any.
11. **A word or character diff cuts on UAX #29 boundaries.**
    `DiffWords` uses the word boundaries and `DiffGraphemes` the
    extended grapheme cluster boundaries, both from
    [UAX #29](https://www.unicode.org/reports/tr29/). A combining
    accent and a family emoji are therefore each one token, and a
    character diff never hands a renderer half a codepoint sequence.
12. **`diffscript.ratio` is `difflib`'s similarity measure.** It is
    twice the number of matched tokens divided by the total length of
    both inputs, so it runs from 0.0 to 1.0.
13. **`diffrender.side_by_side_into` needs a width function.** Column
    layout has to know how many terminal cells a string occupies, and a
    `core` package cannot decide that for you.
    [unicode-nv](https://novo-lang.org/packages/unicode-nv)'s
    `uwidth.cluster_width` is the usual argument.

## What is not included

- **Reading or writing files.** Every function here takes the text as
  an argument. `unified_to` and `side_by_side_to` take a writer the
  caller supplies, and cost whatever that writer costs.
- **Running on a microcontroller.** The package makes no such claim and
  carries no device probe. An edit script, the two token tables and the
  Myers path array are all heap allocations whose size follows the
  input. A device diffing two configuration blobs needs a
  fixed-capacity surface, which would be a different set of functions
  rather than an annotation on these.
- **Binary diffing.** No bsdiff, no delta compression and no rolling
  hash. Every input here is text cut into tokens.
- **Directory and repository diffing.** One pair of texts at a time. A
  caller walking a tree calls this once per file pair.
- **Rendering colour.** `diffrender.lines` answers rows with a kind,
  and the caller chooses the attributes.
- **The `git diff` extended headers.** Rename detection, mode changes
  and index lines are git's format rather than the unified one.
  `diffpatch.file_mode` reports only whether a parsed file patch
  creates or deletes a file.

## Related packages

- [unicode-nv](https://novo-lang.org/packages/unicode-nv) is the only
  dependency. `DiffWords` and `DiffGraphemes` are its word and cluster
  boundaries, and `diffunit.word_segments` answers its `UniWord` values
  directly. The line granularity and the algorithms use none of it.
- [fuzzy-nv](https://novo-lang.org/packages/fuzzy-nv) answers how
  similar two strings are and where a needle matched. It is for ranking
  candidates. This package is for describing an edit.
- [textwrap-nv](https://novo-lang.org/packages/textwrap-nv) wraps the
  columns a side-by-side diff produces, when a caller wants wrapping
  rather than truncation.

## Tests

The reference implementation for the API shape is the Rust crate
**`similar`**: four operation variants, the algorithm as an enum,
inline refinement as a separate call, and a three-way merge beside the
two-way diff. Python's **`difflib`** supplies `ratio` and its opcode
vocabulary, and cases from its `test_difflib` are in the suite.

The rendered output is compared against GNU diffutils byte for byte,
because a unified diff is an interchange format that `patch(1)` and
`git apply` both read. GNU patch's testsuite supplies the fuzz and
offset cases and `git apply`'s `t4xxx` tests supply the strict ones;
the two disagree, which is why both option sets are published. The
merge cases come from git's `t6xxx` tests and from `diff3`.

The algorithms are Myers 1986, whose section 4 examples are in the
suite, Bram Cohen's patience diff, and JGit's histogram diff.

```bash
novo test tests/diffunit_tests.nv      #  7 tests: tokens, policies, the two intervals
novo test tests/diffscript_tests.nv    # 10 tests: the three walks and the bound
novo test tests/diffrender_tests.nv    # 10 tests: unified output and the row list
novo test tests/diffpatch_tests.nv     #  8 tests: parsing, offset, fuzz and rejects
novo test tests/diffmerge_tests.nv     #  9 tests: clean merges, conflicts and markers
```

The suite asserts that a byte span and a token range cannot be
confused, that an ignore-whitespace policy changes the numbering and
not the rendered bytes, that a bounded walk reports itself as not
minimal, that two identical inputs produce one equal operation rather
than none, that a `@@` header matches what `diff -u` writes, that a
context line beginning with a minus sign is not painted as a deletion,
that a partly applied patch answers both the text and the rejects, and
that a merge of a file containing marker lines is not corrupted by its
own output.

The tests compile today and fail at run, each on the
`not implemented: diff-nv.<module>.<fn>` panic that is its body. That
is the expected state of an interface release. They turn green one at a
time as bodies land.

## Implementation status

Nothing is implemented. The table lists the surface an implementation
has to fill.

| Item | Implemented |
| --- | --- |
| `diffunit.exact_policy`, `.ignore_space_policy` | no |
| `diffunit.tokenize`, `.tokenize_with`, `.tokenize3`, `.tokenize_one`, `.intern_pair` | no |
| `diffunit.token_count`, `.token_span`, `.token_str`, `.token_unterminated`, `.line_of_byte` | no |
| `diffunit.range_span`, `.span_str`, `.range_len`, `.range_empty` | no |
| `diffunit.grapheme_boundary`, `.word_segments` | no |
| `diffscript.default_options`, `.minimal_options`, `.patience_options`, `.histogram_options` | no |
| `diffscript.diff`, `.diff_ids`, `.common_subsequence`, `.refine` | no |
| `diffscript.hunks`, `.counts`, `.ratio`, `.unchanged`, `.invert` | no |
| `diffscript.op_a`, `.op_b`, `.op_changed` | no |
| `diffrender.unified_options`, `.unified_options_named`, `.column_options` | no |
| `diffrender.unified`, `.unified_into`, `.unified_to`, `.hunk_header_into` | no |
| `diffrender.lines`, `.inline_marks`, `.stat_line_into` | no |
| `diffrender.side_by_side_into`, `.side_by_side_to` | no |
| `diffpatch.apply_options`, `.strict_apply_options` | no |
| `diffpatch.parse_unified`, `.error_line`, `.patch_of`, `.script_of` | no |
| `diffpatch.apply`, `.apply_into`, `.rejects_empty`, `.reject_file_into` | no |
| `diffpatch.strip_path`, `.file_mode` | no |
| `diffmerge.merge_options`, `.diff3_options`, `.markers` | no |
| `diffmerge.merge3`, `.merge3_into`, `.merge_tokens`, `.conflicts_only` | no |
| `diffmerge.clean`, `.conflict_into`, `.has_marker_lines` | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
