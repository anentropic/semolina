# Phase 49: `.into(DTO)` Typed Results - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-13
**Phase:** 49-into-dto-typed-results
**Areas discussed:** Streaming DTO shape, Pre-check strictness, Missing-package errors, Polars Decimal (inherited gap)

---

## Pre-discussion (assumptions session, same day)

Ran `/gsd-discuss-phase 49 --assumptions` first. Four corrections came out of it, three of
which were settled before this discussion began.

| Question | Options | Selected |
|---|---|---|
| Conversion path | arrowmodel fast path default + `validate=` passthrough | ✓ |
| | Validated by default | |

**Notes:** The user directed the fast path with a pass-through `validate=True` argument, and
supplied `https://anentropic.github.io/arrowmodel/how-to/use-validated-mode.html` — *"if in
doubt check the docs"*. Fetching it confirmed `validate` is a keyword on `convert()` across all
three arrowmodel API styles, that the fast path uses `model_construct` and raises nothing, and
that the validated path costs 2–5x and stops at the first failing row.

| Question | Options | Selected |
|---|---|---|
| Where does DTO-03's error come from, given the fast path validates nothing? | Structural pre-check, always | ✓ |
| | Only under `validate=True` | |

**Notes:** The user asked whether the pre-check adds a database round trip. It does not —
Arrow's C stream delivers the schema when the stream is established, so `reader.schema` and
`Table.schema` are property reads on objects already in memory. Confirming that settled it.

| Question | Options | Selected |
|---|---|---|
| Where does `.into()` live? | Cursor only | ✓ |
| | Cursor + eager `Query` terminal | |

**Notes:** The user asked for this one to be clarified rather than answered first time; it was
re-presented with concrete call sites for both shapes and the asymmetry named (streaming has to
stay on the cursor regardless, because of reader lifetime rules).

| Question | Options | Selected |
|---|---|---|
| DTO-05, whose premise was found to be false | Reword it | ✓ |

**Notes:** Grounding turned up that `semolina` → `adbc-poolhouse` → `pydantic-settings>=2.0.0`
→ `pydantic>=2.7.0` is unconditional and predates v0.7, so the requirement's promise that a
default install pulls no pydantic had never been true. Reworded and committed as `f87290f`
before planning.

---

## Streaming DTO shape

| Option | Description | Selected |
|--------|-------------|----------|
| Flattened — one DTO at a time | Mirrors the existing `for row in cursor`; converts a batch internally, yields DTOs one by one | ✓ |
| Batched — `list[DTO]` per batch | Exposes Arrow's batch granularity; matches DTO-02's literal wording | |
| Both | Batched primitive, flattened wrapper | |

**User's choice:** Flattened.
**Notes:** The batched option was selected first and then reversed — *"we should do it the
other way - instantiate as a batch but yield individual instances like we do for Row"*. Both
halves matter: convert per batch (that is where arrowmodel's Rust speed lives) but hand back
instances singly.

| Option | Description | Selected |
|--------|-------------|----------|
| `iter_into(DTO)` | Verb-first, matching `fetch_arrow_table` / `fetch_record_batch` | ✓ |
| `into_iter(DTO)` | Sorts beside `into()` in autocomplete; noun-first, Rust-ish | |
| `stream_into(DTO)` | Names the behaviour; matches the streaming how-to's vocabulary | |

**User's choice:** `iter_into(DTO)`.

| Option | Description | Selected |
|--------|-------------|----------|
| At the call — fail fast | Pre-check runs immediately, then returns the generator | (withdrawn) |
| On first iteration — plain generator | One generator function, check at the top of the body | (withdrawn) |

**User's choice:** None — the question was withdrawn. The user asked whether "fail fast" meant
executing the query and inspecting the first batch. It does not, and the clarification showed
the question was badly framed: both options cost the same, because reading the schema pulls no
batch and issues no query. Taken as Claude's discretion instead, resolving to fail-fast.

---

## Pre-check strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Fine — ignore silently | The DTO is a projection; unclaimed columns are dropped, as arrowmodel already does | ✓ |
| Error — demand an exact match | The DTO must account for every column | |
| Fine by default, strict on request | `exact=True` keyword | |

**User's choice:** Ignore extras.

| Option | Description | Selected |
|--------|-------------|----------|
| Always an error | Every declared field must be backed by a column, defaults included | |
| Defaulted fields may be absent | A field with a default is optional in the result | ✓ |

**User's choice:** Defaults excuse absence.
**Notes:** Flagged for research — whether arrowmodel itself tolerates a declared field with no
matching Arrow column. If it errors first, this allowance only relocates the failure.

| Option | Description | Selected |
|--------|-------------|----------|
| Subtype-tolerant | Passes when the annotation can legally hold the mapped type; `Any`/`object` opt out; `Decimal`→`float` fatal | ✓ |
| Strict equality | Annotation must equal the mapped type exactly | |
| Reject only known-lossy | Curated list of bad pairings | |

**User's choice:** Subtype-tolerant.

**Not asked — decided on evidence:** nullability is not checked at all. `47-DECISIONS.md`
measured the Arrow nullable flag as `True` for all seven DuckDB fields including COUNT, so
checking it would flag essentially every field on every query.

**Not asked — free either way:** the error reports every mismatched field at once.

---

## Missing-package errors

| Option | Description | Selected |
|--------|-------------|----------|
| No extras — name the package | `pip install polars`; Semolina doesn't claim what it doesn't import | |
| Add extras — one install idiom | `[pandas]` / `[polars]` join `[async]` / `[duckdb]` / `[arrowmodel]` | ✓ |
| No extras — name both routes | Plain install plus a mention of `[all]` | |

**User's choice:** Add the extras.
**Notes:** Presented with the asymmetry that Semolina never imports pandas or polars — the ADBC
driver does. The user took consistency over strict dependency honesty.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — `all` means all | `[all]` gains all four new extras | ✓ |
| No — `all` stays backends + async | Result-shaping extras chosen deliberately | |
| Yes, but polars stays out | polars excluded as the known-partial one | |

**User's choice:** `all` means all.
**Notes:** Selected "No" first, then corrected immediately — *"sorry, no, all means all"*.
This is what makes the polars measurement below possible, since CI runs
`uv sync --all-groups --extra all`.

| Option | Description | Selected |
|--------|-------------|----------|
| Flat, matching what's there | Two `Semolina*Error(RuntimeError)` in a new `exceptions.py` | ✓ |
| Introduce a `SemolinaError` base | Reparent all four; one `except` clause for app backends | |
| Reuse stdlib types | `ModuleNotFoundError` / `TypeError` with better messages | |

**User's choice:** Flat. Nothing outside the phase changes.

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — same guard, same error | pyarrow guarded on all four Arrow/dataframe methods | ✓ |
| No — log it as a todo | Keep to RESULT-02's literal wording | |
| Make pyarrow a base dependency | Stop pretending it's optional | |

**User's choice:** In scope.
**Notes:** Raised because grounding found a pre-existing hole nobody had named — ADBC guards
its own pyarrow import, and Semolina declares pyarrow only inside `[duckdb]`, so a base install
plus a warehouse extra can already fail obscurely on `fetch_arrow_table()`.

---

## Polars Decimal (inherited gap)

| Option | Description | Selected |
|--------|-------------|----------|
| Measure it and close A3 | Run Phase 47's measurement now that polars is installed; regenerate the artifact | ✓ |
| Measure, document a caveat if needed | Same measurement, obligation scoped to reporting | |
| Leave A3 open | Ship the passthrough unmeasured | |

**User's choice:** Measure and close.

| Option | Description | Selected |
|--------|-------------|----------|
| Dated correction in the body | Leave the original text, append a dated note; `46-VERIFICATION.md` precedent | ✓ |
| Artifact only — Phase 48's rule | Regenerate the artifact, leave `47-DECISIONS.md` untouched (D-10 precedent) | |
| Edit the sentence in place | Rewrite the polars bullet | |

**User's choice:** Dated in-body correction.
**Notes:** The project has both precedents. The distinction that decided it: Phase 48's D-10
superseded generated cell values, whereas this supersedes a normative claim about what is known.

---

## Claude's Discretion

- Fail-fast timing for `iter_into()`, and the implementation consequence that it must not be a
  bare generator function.
- Reporting all schema mismatches at once rather than the first.
- Detection mechanism for missing packages (Phase 47's `find_spec` precedent).
- DTO-06's docs shape — how-to vs tutorial, and the scenario. Governed by
  `.claude/skills/semolina-docs-author/SKILL.md`.
- arrowmodel's version floor.

## Deferred Ideas

- `Query.into(DTO)` eager terminal — rejected here, purely additive later.
- `into_batches()` — rejected.
- `SemolinaError` common base class — rejected; touches errors outside the phase.
- Making `pyarrow` a base dependency — rejected in favour of the guard; may be worth revisiting
  as a project-level decision.
- STREAM-04 user-controllable batch size — already deferred to a later milestone.
- `into(DTO, check=False)` escape hatch — raised, not pursued.
- Runtime type coercion on `Row` construction — reviewed and explicitly NOT folded; it asks for
  what Phase 47 Decision 1 prohibits.
