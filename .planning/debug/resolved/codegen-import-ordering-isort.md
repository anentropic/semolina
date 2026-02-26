---
status: resolved
trigger: "Generated Python model code from render_views() produces imports that are not isort-sorted, causing ruff lint failures"
created: 2026-02-25T00:00:00Z
updated: 2026-02-25T21:00:00Z
---

## Current Focus

hypothesis: Template hard-codes third-party cubano import first; format_with_ruff only runs ruff format (not ruff check --fix), so isort is never applied
test: Confirmed by reading template, renderer, and running ruff check --select I against sample output
expecting: N/A - root cause confirmed
next_action: DONE - root cause found, diagnosis returned

## Symptoms

expected: Generated Python source passes ruff lint (including isort rule I001)
actual: Generated source has `from cubano import ...` before `from typing import Any`, violating isort stdlib-before-third-party ordering; ruff lint reports I001
errors: "I001 [*] Import block is un-sorted or un-formatted"
reproduction: Call render_views() with a view containing a field whose data_type is None (produces Any); inspect the import block in the returned string
started: Always - template was written with cubano import first

## Eliminated

(none - root cause found on first investigation)

## Evidence

- timestamp: 2026-02-25T00:00:00Z
  checked: src/cubano/codegen/templates/python_model.py.jinja2 lines 1-7
  found: |
    Line 1: `from cubano import SemanticView, Metric, Dimension, Fact`  (unconditional)
    Line 2-4: `{% if needs_datetime %}import datetime{% endif %}`
    Line 5-7: `{% if needs_any %}from typing import Any{% endif %}`
  implication: cubano (third-party) is always emitted before typing (stdlib); isort requires stdlib first

- timestamp: 2026-02-25T00:00:00Z
  checked: src/cubano/codegen/python_renderer.py format_with_ruff() (lines 191-219)
  found: |
    Runs: `uv run ruff format --stdin-filename models.py -`
    `ruff format` handles only whitespace/style formatting (Black-equivalent).
    It does NOT run import sorting (that is `ruff check --fix --select I`).
  implication: render_and_format() never corrects import order; isort is never applied to generated code

- timestamp: 2026-02-25T00:00:00Z
  checked: live ruff check --select I against sample output
  found: |
    Input:
      from cubano import SemanticView, Metric, Dimension, Fact
      from typing import Any
    ruff reports: I001 [*] Import block is un-sorted or un-formatted (exit 1)
  implication: Confirms the output as-is fails isort; the fix must either reorder the template or run ruff check --fix

## Resolution

root_cause: |
  The Jinja2 template `python_model.py.jinja2` unconditionally emits the third-party
  `from cubano import ...` line FIRST (line 1), then conditionally emits stdlib imports
  (`import datetime`, `from typing import Any`) after it.
  isort rules require stdlib imports before third-party imports, so the output violates I001.

  Compounding this: `format_with_ruff` only invokes `ruff format` (the Black-equivalent
  formatter), which handles whitespace and style but does NOT sort imports.
  Import sorting requires `ruff check --fix --select I` as a separate pass.
  Since neither the template nor the post-processing step produces correctly-ordered imports,
  any generated file that includes `import datetime` or `from typing import Any` will fail
  `ruff check`.

fix: N/A - diagnose only
verification: N/A
files_changed: []
