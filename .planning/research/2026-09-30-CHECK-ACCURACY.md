# `--check` accuracy: false positives, false negatives and alternative designs

**Date:** 2026-09-30. **Feeds:** Phase 55 (GEN-11, GEN-12, decision D9).
**Prompted by:** 52-06's model inheritance, which `semolina codegen --check` cannot follow,
and the question whether the check's text-reading design should change.

Both `--check` commands read a committed file as text (`ast.parse`, never imported) and
compare it with what the warehouse would produce today:

| Command | Reader | Comparison |
|---------|--------|------------|
| `semolina codegen --check --model F` | `codegen/model_reader.py` | `codegen/annotation_check.py`: annotation strings, plus role and resolved column |
| `semolina codegen-dto --check` | `codegen/dto_reader.py` | `codegen/dto_check.py`: annotation strings and `validation_alias` |

Why text and not import is recorded in both readers' docstrings: importing runs the file's
module-level code in a process that holds warehouse credentials (threat T-48-19; the threat
entry itself is not in the repo any more); the file must be importable as a package member;
and an import resolves annotations, so `JsonValue` comes back as a `ForwardRef` rather than
the text codegen compares against. The other codegen routes *do* import, deliberately: a
dotted query path for `codegen-dto` (T-50-02) and a dotted `--backend`.

## The case corpus

"Verified" means reproduced on 2026-09-30 by running the reader on a sample file. "From the
code" means read from the comparison logic, where the behaviour is unconditional. Each case
should become a test in 55-06, whatever D9 decides.

### `codegen --check` (models)

False positives: drift is reported for a model that is correct.

| # | Case | Cause | Evidence |
|---|------|-------|----------|
| M1 | `Optional[str]`, `None \| str`, `Decimal \| None` after `from decimal import Decimal`, `'str'` | exact string equality against codegen's spelling | verified: kept verbatim by the reader |
| M2 | `semolina.Metric[T]()`, `M[T]()` from `from semolina import Metric as M`, `x: Dimension[str] = Dimension[str]()` | the reader recognises only `Name[...]()` with the bare names `Metric`/`Dimension`/`Fact` in a plain assignment | verified: silently skipped, then reported absent |
| M3 | `view=VIEW` with a module constant | the reader accepts only a string literal | verified: class skipped, every field absent |
| M4 | CLI view spelled differently from `view=` (`analytics.sales` vs `sales`, or case) | models are matched to views by exact string | from the code (`cli/codegen.py`, `by_view`) |
| M5 | attribute renamed, same column kept with `source=` | fields matched by attribute name, not resolved column | from the code (`committed_fields.pop(field.name)`) |
| M6 | fields inherited from a base class | the reader reads each class body alone | known since 52-06, documented in `how-to/models.rst` |
| M7 | untyped `Metric()` | recorded as `Any`, compared with `Any \| None` | already GEN-09 (review A32) |

False negatives: a real problem is not reported.

| # | Case | Cause | Evidence |
|---|------|-------|----------|
| M8 | probe unavailable, every row compared against the catalogue | the fallback compares the model with the source that wrote it; the exit code depends on drift only | already GEN-09 (review A33); the one most likely to hide drift in CI |
| M9 | two classes declaring the same view | `by_view` is a dict, last class wins | from the code |
| M10 | a filtered query's result shape | the probe is always the unfiltered query | documented; a filter should not change column types |

### `codegen-dto --check` (DTOs)

| # | Kind | Case | Cause | Evidence |
|---|------|------|-------|----------|
| D1 | FP | `Optional[decimal.Decimal]` vs `decimal.Decimal \| None` | exact string equality | verified: `_annotations_agree` returns False |
| D2 | FP | field hand-edited to `alias=` or `AliasChoices(...)` | reader keys on a string `validation_alias=` | verified: skipped, reported as omitted |
| D3 | FP | deliberate narrowing (`float` for a decimal column) used with `.into(..., validate=True)` | the check compares with the fast path's exact type; the docs call the narrowing legitimate | from the code and `how-to/typed-results.rst` |
| D4 | FP | class renamed by hand | classes matched by name | from the code (`by_name`) |
| D5 | FN | any committed annotation against a generated `Any` | deliberate and documented: codegen tells you to replace `Any` | verified |

Docs: `how-to/codegen.rst` says "Only an annotation moves a row to `drift`", which M1 and M2
contradict.

## Alternatives for D9

Not exclusive: the likely answer combines two or three.

**A. Harden the text reader.** Keep `ast.parse`, and resolve names through the file's own
import statements: `semolina.Metric`, `from semolina import Metric as M`, `from decimal
import Decimal`. Accept `AnnAssign`. Read module-level string constants for `view=`. Follow
base classes defined in the same file. Warn about any statement that looks like a field but
isn't recognised, rather than skipping it silently. Fixes M2, M3, most of M6 (bases in other
files would get one warning line, not a row per field), D2, and makes M1 fixable with B.
Cost: the reader grows into a partial name resolver.

**B. Compare resolved types, not strings.** Evaluate both annotations without importing the
user's file: walk the annotation's AST, allowing only `Name`, `Attribute`, `Subscript`,
`BinOp(|)`, `Tuple` and `Constant(None)`, and resolve names against an allowlist (`builtins`,
`typing`, `decimal`, `datetime`, `uuid`, `semolina.types`, `pydantic`). There are no calls, so
nothing of the user's runs. Measured 2026-09-30 on Python 3.11, 3.13 and 3.14:
`int | None`, `None | int`, `Optional[int]` and `Union[None, int]` all compare equal once
evaluated, as does `decimal.Decimal | None` against `Optional[decimal.Decimal]`. Fixes M1 and
D1. Needs A's import resolution for `Decimal` imported bare. An annotation outside the
allowlist falls back to string comparison and says so.

**C. Import the committed file, opt-in.** For example `--import`, and possibly in a
subprocess that has no warehouse credentials: the child imports the file, serialises
`_fields`, `__orig_class__` and aliases as JSON, and the parent, which holds the credentials,
compares. That answers T-48-19's core concern, credentials next to untrusted code, while
getting inheritance, aliases, constants and cross-file bases for free. Cost: the file must be
importable; `JsonValue` needs special handling; and it is a second code path to maintain. It
also has to be measured: does a credential-free child cover every way a module can reach
credentials (`.semolina.toml` on disk, `.env`)?

**D. A runtime check API for the user's own test suite.** For example
`semolina.testing.check_model(Sales, engine)` and `check_dto(RevenueByCountry, query,
engine)`. The user's tests already import their models, so the trust decision is theirs, and
inheritance, aliases and resolved types come free. It complements the CLI rather than
replacing it, since CI jobs without a test suite still want the CLI.

**E. For DTOs, judge by what `.into()` accepts.** Replace string equality with the fast
path's own `check_result_schema` semantics (`_annotation_accepts`, including CORE-11's
refusals) plus the alias. Optionally add `--validate` to judge by `validate=True` instead,
which fixes D3. This needs resolved types, so it depends on B, C or D. It has one appeal of
its own: `--check` and `.into()` could never disagree about a DTO.

**F. A generation manifest.** Embed the generated annotations (or a hash of them) in the
file's header. `--check` could then tell "you edited this" apart from "the warehouse moved".
This addresses hand edits in general, not any single case above. Weigh it last: it adds a
format to maintain.

## Open questions for the D9 checkpoint

1. Is a hand-edited generated file a supported input, or should `--check` treat any edit as
   drift by design? The answer decides how far A goes.
2. Does C's credential-free subprocess actually isolate credentials? Measure it before
   relying on it.
3. Should M8, a check that never probed, fail by default (a distinct exit code, GEN-09) or
   only under a strict flag?
4. Is D worth its API surface in v0.7, or is it a v0.8 item?
