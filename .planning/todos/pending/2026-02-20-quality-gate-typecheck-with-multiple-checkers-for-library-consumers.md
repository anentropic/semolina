---
created: 2026-02-20T23:31:59.453Z
title: Quality gate typecheck with multiple checkers for library consumers
area: tooling
files: []
---

## Problem

The project currently uses basedpyright as its sole type checker in the quality gate (`uv run basedpyright`). For a library published on PyPI, this is insufficient — library consumers may use different type checkers (mypy, pyright, pyright-strict, basedpyright) with different inference rules and stubs resolution. A type annotation that passes basedpyright may still produce errors under mypy or vanilla pyright.

To provide a good experience for library consumers using any type checker, cubano should validate its public API against multiple type checkers as part of CI/quality gates.

## Solution

Add mypy (and optionally vanilla pyright) to the dev toolchain and quality gate:

1. Add `mypy` to `[project.optional-dependencies] dev` in `pyproject.toml`
2. Configure mypy in `pyproject.toml` under `[tool.mypy]` (strict mode recommended for a library)
3. Add `uv run mypy src/cubano` to the quality gate alongside basedpyright
4. Optionally add pyright (non-based) to catch any divergences
5. Document the multi-checker gate in CONTRIBUTING or the dev workflow docs

Consider using a `py.typed` marker file (PEP 561) if not already present — this signals to type checkers that cubano ships inline type information.
