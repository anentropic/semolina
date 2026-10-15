---
created: 2026-10-15T00:00:00.000Z
title: "Runtime check API for committed models and DTOs (D9's alternative D)"
area: api
target: v0.8
files:
  - src/semolina/codegen/annotation_check.py
  - src/semolina/codegen/dto_check.py
  - .planning/research/2026-10-15-D9-DECISION.md
---

## Problem

Both `--check` commands read a committed file without importing it (D9, griffe). That keeps
a CI run from executing the file, and it also means `--check` can only compare what it can
resolve statically: a user's own annotation type (`Money`) is compared as text, a base
class from an installed package is not followed, and a DTO narrowed on purpose for
`.into(..., validate=True)` reads as drift (D3).

A check that imports the model can see all of it, but D9 measured that a credential-free
subprocess does not keep credentials from the imported code, so the CLI is the wrong place
for it. The user's own test suite already imports their models, and there the trust
decision is plainly theirs.

## Solution

Deferred to v0.8 by D9.7 (2026-10-15). A small public API such as
`semolina.testing.check_model(Model, engine)` / `check_dto(DTO, query, engine)` that a test
calls with live classes: it probes the result schema the same way `--check` does and
compares against the class's runtime annotations (`__orig_class__`, `model_fields`). Could
take a `validate=True` mode for D3. Reuse `annotation_check` and `dto_check` rather than a
second comparison.
