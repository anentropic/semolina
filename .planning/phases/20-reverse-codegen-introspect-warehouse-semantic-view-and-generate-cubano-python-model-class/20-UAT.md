---
status: resolved
phase: 20-reverse-codegen-introspect-warehouse-semantic-view-and-generate-cubano-python-model-class
source: 20-01-SUMMARY.md, 20-02-SUMMARY.md, 20-03-SUMMARY.md, 20-04-SUMMARY.md, 20-05-SUMMARY.md
started: 2026-02-24T07:30:00Z
updated: 2026-02-24T12:00:00Z
---

## Current Test

number: 6
name: Snowflake introspection (skip if no live connection)
expected: |
  With Snowflake credentials configured, run:
    cubano codegen <your_schema.semantic_view_name> --backend snowflake
  Output: valid Python class with Metric(), Dimension(), and/or Fact() fields matching the view.
awaiting: user response

## Tests

### 1. CLI help text
expected: Run `cubano codegen --help` — shows `views` positional arg (multiple) and `--backend`/`-b` option. No old forward codegen flags.
result: pass

### 2. Invalid backend exits with error
expected: Run `cubano codegen some.view --backend badvalue` — exits with code 1 and a message indicating the backend is invalid/unknown. No Python traceback.
result: pass

### 3. Generated output structure
expected: |
  Run `cubano codegen --help` or look at the how-to docs.
  The generated output for any view should have:
  - A single `from cubano import SemanticView, Metric, Dimension, Fact` imports line at the top
  - One class per view, named in PascalCase from the view name
  - Fields declared as `Metric()`, `Dimension()`, or `Fact()` assignments
result: pass

### 4. How-to guide content
expected: |
  Open docs/src/how-to/codegen.md (or the built docs site).
  The page should describe the REVERSE codegen workflow: introspecting a warehouse view to produce a Python class.
  It should show `cubano codegen <view_name> --backend snowflake|databricks` as the primary command.
  No references to old forward codegen (Python file → SQL/YAML).
  The "Understand the generated output" section should show warehouse DDL SQL before the CLI command.
result: issue
reported: "Exit codes — let's use distinct error codes for different error cases"
severity: minor

### 5. Reference pages for new modules
expected: |
  The docs reference section should have pages for:
  - cubano.codegen.introspector (IntrospectedField, IntrospectedView)
  - cubano.codegen.type_map (snowflake_json_type_to_python, databricks_type_to_python)
  - cubano.codegen.python_renderer (render_views, render_and_format)
  And NO pages for: generator, loader, renderer, validator (those modules were deleted).
result: pass

### 6. Snowflake introspection (skip if no live connection)
expected: |
  With Snowflake credentials configured, run:
    cubano codegen <your_schema.semantic_view_name> --backend snowflake
  Output should be a valid Python class with Metric(), Dimension(), and/or Fact() fields
  matching the view's column definitions. Python source is printed to stdout.
result: [pending]

### 7. Databricks introspection (skip if no live connection)
expected: |
  With Databricks credentials configured, run:
    cubano codegen <catalog.schema.metric_view_name> --backend databricks
  Output should be a valid Python class with Metric() and Dimension() fields
  (no Fact() — Databricks has no native fact type).
result: [pending]

## Summary

total: 7
passed: 4
issues: 1
pending: 2
skipped: 0

## Gaps

- truth: "Exit codes are distinct per error type (invalid backend, view not found, connection error)"
  status: resolved
  reason: "User reported: Exit codes — let's use distinct error codes for different error cases"
  severity: minor
  test: 4
  artifacts: []
  missing: []
