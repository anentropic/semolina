---
phase: 45-databricks-adbc-query-support
reviewed: 2026-06-24T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/semolina/engines/sql.py
  - tests/unit/test_sql.py
findings:
  critical: 1
  warning: 2
  info: 2
  total: 5
status: issues_found
---

# Phase 45: Code Review Report

**Reviewed:** 2026-06-24
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Phase 45 introduces a deliberate SQL-injection surface: the Databricks dialect
inlines WHERE-clause literals into the SQL string (because the ADBC driver
rejects bound `?` params), while Snowflake/DuckDB keep the parameterized path.

The string escaping in `render_literal` itself is correct for both the
standard-SQL (`SnowflakeDialect`) and Spark (`DatabricksDialect`) paths
(backslash-before-quote ordering is right, type dispatch is ordered correctly
with `bool` before `int`, unsupported types raise `NotImplementedError`).

However, the **post-pass that performs the substitution** (`_render_literal_sql`)
has a confirmed BLOCKER: it replaces placeholders by string-matching `"?"` against
the SQL, but a rendered literal can itself contain a `?` (any user value with a
`?` in it), which then gets matched and overwritten by the *next* parameter. This
corrupts quoting, mis-pairs values, and can leave a stray `?` in the SQL paired
with empty params — the exact "mixed mode" failure the phase brief flagged. A
second WARNING covers `float('inf')`/`nan` rendering as bare identifiers, and the
test suite has a coverage gap that lets both of these slip through untested.

## Critical Issues

### CR-01: `_render_literal_sql` re-matches `?` inside already-inlined literals (SQL corruption / injection)

**File:** `src/semolina/engines/sql.py:850-854`
**Issue:**
The substitution loop replaces the placeholder string `"?"` one occurrence at a
time, left to right:

```python
result = sql_template
ph = self.dialect.placeholder            # "?"
for param in params:
    result = result.replace(ph, self.dialect.render_literal(param), 1)
return result
```

`str.replace(ph, ..., 1)` always replaces the *first* remaining `?` in the
**whole accumulated string** — including any `?` that an earlier
`render_literal(param)` just inlined. Because `render_literal` does not (and
cannot meaningfully) escape `?` inside a string literal, a user value containing
`?` makes the next parameter land in the wrong place.

Confirmed reproduction (Databricks, `Exact("country", "a?b") & Exact("region", "WEST")`):

```text
WHERE (`country` = 'a'WEST'b' AND `region` = ?)
params: []
```

Three things go wrong at once:
1. The first literal becomes `'a'WEST'b'` — the second value (`WEST`) is spliced
   into the middle of the first value's quotes, breaking quoting and producing an
   injectable/garbled fragment.
2. The second `?` is consumed by the first value's `?`, so the genuine second
   placeholder is **never filled**.
3. A literal `?` is left in the final SQL but `params == []`, so it is sent to
   Databricks unbound (the very mixed-mode state this phase was meant to prevent).

This is reachable from any normal query (multi-filter `And`, `In`-list, or even a
single value that contains `?`, e.g. a search string `"why?"`). It is both a
correctness bug (wrong/failed queries) and a safety bug (broken quoting around
attacker-controlled text).

**Fix:** Do not re-scan the growing result. Split the template on the placeholder
once and interleave the rendered literals, so already-inlined `?` characters are
never reconsidered. Also assert the placeholder count matches the param count.

```python
def _render_literal_sql(self, sql_template: str, params: list[Any]) -> str:
    ph = self.dialect.placeholder
    segments = sql_template.split(ph)
    if len(segments) - 1 != len(params):
        msg = (
            f"Placeholder count ({len(segments) - 1}) does not match "
            f"param count ({len(params)}); cannot safely inline literals."
        )
        raise ValueError(msg)
    out = [segments[0]]
    for literal_value, tail in zip(
        (self.dialect.render_literal(p) for p in params), segments[1:], strict=True
    ):
        out.append(literal_value)
        out.append(tail)
    return "".join(out)
```

(`render_inline`, the display-only sibling at lines 856-875, has the identical
flaw. It is documented as "never for execution", so it is not itself a security
BLOCKER, but it produces misleading debug SQL for the same inputs and should get
the same split-and-interleave fix — see IN-02.)

## Warnings

### WR-01: `float('inf')` / `float('nan')` render as bare identifiers, not literals

**File:** `src/semolina/engines/sql.py:113` (Snowflake/base) and `:406` (Databricks)
**Issue:**
The numeric path is `return repr(value)`. For `float`, `repr` emits `inf`,
`-inf`, and `nan`:

```text
render_literal(float('inf')) -> 'inf'
render_literal(float('nan')) -> 'nan'
```

These are not valid SQL numeric literals. Inlined into `revenue > inf`, the
warehouse parses `inf`/`nan` as a bare **column reference** (identifier), so the
query either errors or — worse — silently compares against a column instead of
the intended value. Unlike the parameterized path (where the driver handles the
float), the inlined path emits this directly into SQL text. Scientific notation
(`1e+20`) is fine; only the three non-finite values are broken.

**Fix:** Reject non-finite floats explicitly so the caller fails loudly rather
than emitting an identifier:

```python
import math
...
if isinstance(value, int | float):
    if isinstance(value, float) and not math.isfinite(value):
        msg = f"Cannot render non-finite float as SQL literal: {value!r}."
        raise NotImplementedError(msg)
    return repr(value)
```

### WR-02: No test exercises an inlined value containing `?` (the CR-01 gap)

**File:** `tests/unit/test_sql.py:905-941` (`TestDatabricksLiteralInlining`)
**Issue:**
The adversarial inlining tests cover `"US"`, `["US", "CA"]`, and `"O'Reilly"` —
none contain a `?`, and none use two placeholders where an earlier value carries a
`?`. The phase brief explicitly called out "embedded `?`" and multi-placeholder
ordering as required adversarial inputs; the suite would pass green while CR-01
ships. There is likewise no test for `float('inf')`/`nan` (WR-01).

**Fix:** Add regression tests that assert both the SQL string and `params == []`:

```python
def test_value_containing_question_mark_does_not_misplace_later_params(self):
    pred = Exact("country", "a?b") & Exact("region", "WEST")
    query = replace(
        _Query().metrics(Sales.revenue).dimensions(Sales.country),
        _filters=pred,
    )
    sql, params = SQLBuilder(DatabricksDialect()).build_select_with_params(query)
    assert "`country` = 'a?b'" in sql
    assert "`region` = 'WEST'" in sql
    assert params == []

def test_non_finite_float_raises(self):
    with pytest.raises(NotImplementedError):
        DatabricksDialect().render_literal(float("inf"))
```

## Info

### IN-01: `str` subclasses silently pass the `isinstance(value, str)` path

**File:** `src/semolina/engines/sql.py:114` and `:407`
**Issue:**
`isinstance(value, str)` accepts `str` subclasses (e.g. `enum.StrEnum` members,
or a user-defined `class S(str)`). These render via the normal quoting path, which
is escaping-safe, so this is not an injection issue — but a `StrEnum` member would
render its `str` value rather than raising, which may surprise callers who expect
only plain supported types. Acceptable as-is; noting for awareness. No fix
required unless strict type fidelity is desired.

### IN-02: `render_inline` shares CR-01's re-scan flaw (display only)

**File:** `src/semolina/engines/sql.py:871-875`
**Issue:**
`render_inline` uses the same `result.replace(ph, repr(param), 1)` loop and will
mis-place params for values containing `?` (and `repr` of a string also contains
no `?`, so the corruption is the same shape as CR-01). It is explicitly
display/debug-only and never executed, so it is not a security defect, but the
debug SQL it produces for such inputs is wrong/misleading.

**Fix:** Apply the same split-and-interleave approach as CR-01's fix (substituting
`repr(param)` for `render_literal(param)`), or factor the interleave logic into a
shared helper that both methods call with a different renderer callable.

---

## Structural Findings (fallow)

No structural findings block was provided for this review.

---

_Reviewed: 2026-06-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
