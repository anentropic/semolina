---
phase: 46
plan: "01"
subsystem: packaging-and-lint
tags: [packaging, dependencies, lint, ruff, async, posture-a]
status: complete
requires: []
provides:
  - "adbc-poolhouse>=1.6.1 base floor (sync create_pool now honours config pool_size)"
  - "semolina[async] extra pinning adbc-poolhouse[async]>=1.6.1"
  - "all extra reaching async, so CI's --extra all jobs install the async stack"
  - "trio>=0.33.0 in the dev group for the Trio half of the D-17 loop matrix"
  - "ruff TID251 Posture A gate armed over src/semolina, exempt under tests/"
  - "tests/unit/test_async_packaging.py — the ASYNC-04 packaging contract"
  - "CI packaging-smoke assertion that a base install pulls no anyio"
affects:
  - pyproject.toml
  - uv.lock
  - .github/workflows/ci.yml
  - .planning/REQUIREMENTS.md
  - .planning/ROADMAP.md
tech-stack:
  added:
    - "adbc-poolhouse 1.6.1 (bumped from 1.3.1)"
    - "trio 0.33.0 (dev)"
    - "anyio 4.13.0 (transitive, via adbc-poolhouse[async])"
  patterns:
    - "ruff flake8-tidy-imports banned-api (TID251) as the ASYNC-05 enforcement point"
    - "child-interpreter sys.modules probe for asserting lazy-import packaging contracts"
key-files:
  created:
    - tests/unit/test_async_packaging.py
  modified:
    - pyproject.toml
    - uv.lock
    - .github/workflows/ci.yml
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
decisions:
  - "Floor is >=1.6.1 on both the base pin and the extra, not just the extra, so sync and async agree on pool_size resolution"
  - "TID251 proven non-vacuous by an executed fail-first probe rather than asserted"
  - "ROADMAP SC4 reworded from a textual 'asyncio. reference' scan to what TID251 enforces (import graph), with the dynamic-lookup gap recorded rather than overclaimed"
metrics:
  duration: "~15min"
  completed: 2026-08-01
  tasks: 3
  commits: 3
actuals:
  tokens: 10593
  tasks: 3
  commits: 3
---

# Phase 46 Plan 01: Async Packaging & Posture A Lint Gate Summary

Bumped adbc-poolhouse to 1.6.1, declared the `semolina[async]` extra, and armed a ruff
TID251 gate that is proven to fail on a real `import asyncio` under `src/semolina/`.

## What Was Built

**Task 1 — poolhouse floor bump and the async extra** (commit `e0b3805`)

- Base `[project] dependencies` pin raised `adbc-poolhouse>=1.3.1` → `>=1.6.1`.
- New `[project.optional-dependencies] async = ["adbc-poolhouse[async]>=1.6.1"]`, carrying
  a comment stating why the floor is 1.6.1 and not the 1.5.0 ASYNC-04 originally named.
- `all` changed from `semolina[snowflake,databricks,duckdb]` to
  `semolina[snowflake,databricks,duckdb,async]` — CI's four test jobs all sync with
  `--extra all`, so excluding async would mean the phase's async tests never run there.
- `[dependency-groups] dev` gained `trio>=0.33.0`. `adbc-poolhouse[async]` declares only
  `anyio>=4.13`, and anyio does not vendor Trio, so `all` alone leaves the `[trio]` half of
  every parametrized test erroring at setup.
- `uv.lock` resynced: adbc-poolhouse 1.6.1, anyio 4.13.0, trio 0.33.0 (plus its
  `outcome` / `sniffio` transitives).

**Task 2 — the TID251 Posture A gate** (commit `71f3393`)

- `TID` added to `[tool.ruff.lint] select`.
- `[tool.ruff.lint.flake8-tidy-imports.banned-api]` bans exactly `asyncio` and `anyio`,
  each with a message naming Posture A and ASYNC-05 and pointing at the alternative
  (await poolhouse primitives; a bare `async def` with neutral awaits).
- `[tool.ruff.lint.per-file-ignores]` maps `"tests/**"` to `["TID251"]` per D-14.

**Task 3 — the ASYNC-04 packaging test, the CI assertion, and the floor amendments**
(commit `ac2397d`)

- `tests/unit/test_async_packaging.py`: five tests, all carrying the token `packaging` so
  `pytest -k packaging` selects them. Four parse `pyproject.toml` with `tomllib` and assert
  the declared contract; the fifth spawns a child interpreter via `sys.executable`, imports
  `semolina` there, and asserts `anyio` is absent from *that* process's `sys.modules` —
  necessary because anyio is installed in this dev venv, so an in-process check would be
  vacuous.
- `.github/workflows/ci.yml` `packaging-smoke` gained two steps in the shape of its
  existing pair: a second clean venv with a no-extras install, and a one-liner asserting
  `importlib.util.find_spec('anyio') is None`. The `[duckdb]` steps are untouched.
- `.planning/REQUIREMENTS.md` ASYNC-04 and `.planning/ROADMAP.md` Phase 46 SC4 both now
  name `adbc-poolhouse[async]>=1.6.1` with a one-line evidence note. The ROADMAP
  `**Depends on**` line's poolhouse version was updated too. All edits were scoped `Edit`
  replacements; all five v0.7 phase entries survive.

## Assumption A1 — closed by execution

RESEARCH Assumption A1 (the five existing `DuckDBConfig(database=":memory:", pool_size=1)`
call sites still pass once the floor honours `pool_size=1`) was closed by running the full
root suite against 1.6.1, not by argument.

**Result: 917 passed, 16 skipped, zero failures. No test needed adjustment.**

`tests/unit/test_pool.py` was re-read around its `pool_size=1` reasoning (the
`TestExecuteErrorPathReleasesConnection` docstring at line 367). That docstring argues the
*stricter* case — "with `pool_size=1` a single failed query would permanently consume the
only slot" — which the bump makes literally true rather than aspirational, so it needed no
change. The other four call sites (`tests/conftest.py:132`,
`tests/unit/test_duckdb_engine.py:73,127`, `tests/unit/test_query.py:72`,
`src/semolina/conftest.py:113`) pass unchanged: the `connect` event listener re-seeds data
on every physical connection, so going from five isolated in-memory databases to one is
invisible to them.

Final suite state after all three tasks: **922 passed, 16 skipped**.

## The gate is armed, not nominal (ASYNC-05 prohibition)

The plan carries a kept prohibition: a Posture A gate that can pass vacuously certifies
nothing while reading as green. Two executed probes discharge it.

**Fail-first proof.** A throwaway `src/semolina/_tid_probe.py` containing only
`import asyncio` produced:

```
TID251 `asyncio` is banned: Posture A (ASYNC-05): Semolina library code must stay
loop-agnostic. Await adbc-poolhouse primitives instead.
 --> src/semolina/_tid_probe.py:1:8
Found 1 error.        # exit 1
```

**Scope proof.** The same two imports (`anyio` and `asyncio`) written to
`tests/unit/_tid_scope_probe.py` produced `All checks passed!` (exit 0), confirming the
D-14 carve-out works.

Both throwaway files were deleted; `test ! -e` confirms neither survived.

**Residual evasion path, recorded honestly.** TID251 is import-graph based. A dynamic
module lookup by string name — `importlib.import_module("asyncio")` or
`__import__("asyncio")` — is invisible to it and is deliberately not defended against. That
is why ROADMAP SC4's wording was amended from "any `asyncio.` reference" (which reads as a
textual scan, and which a grep implementation would have failed on this phase's own
docstrings discussing Posture A) to a description of the import graph, with the gap named
in one clause.

The config was verified on both ruff versions in play: `uv run ruff check` uses the
`ruff>=0.15.1` dev dependency, and `prek run --all-files` exercises the
`.pre-commit-config.yaml` `rev: v0.9.6` pin. Both accept it and both pass.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest -q` (A1 closure, Task 1) | 917 passed, 16 skipped |
| `uv run pytest -q` (final state) | 922 passed, 16 skipped |
| `uv run pytest tests/unit -k packaging -q` | 5 passed, 886 deselected |
| `uv run ruff check src/semolina` | All checks passed |
| TID251 fail-first probe (`src/semolina/`) | exit 1 — gate fires |
| TID251 scope probe (`tests/unit/`) | exit 0 — carve-out holds |
| `prek run --all-files` | all hooks Passed (incl. basedpyright strict) |
| poolhouse version + `_resolve_tuning` import | `ok 1.6.1` |
| `create_async_pool` / `close_async_pool` import | `async surface ok` |
| `import trio` | 0.33.0 |
| Base-install lazy-import probe (child interpreter) | `anyio` absent from `sys.modules` |
| `.planning/REQUIREMENTS.md` / `.planning/ROADMAP.md` name `>=1.6.1` | yes, both |
| v0.7 phase entries surviving the scoped ROADMAP edits | 5 of 5 |
| CI `packaging-smoke` anyio step present (yaml-parsed) | `ci step ok` |

## Deviations from Plan

None — plan executed exactly as written. No auto-fixes were needed: the full-suite A1
closure run was green on the first attempt, so no A1-driven test adjustment exists to
record.

One optional deviation worth noting for future runs, though it changed nothing in the
repository: the first `uv sync --all-extras --dev` pruned the locally-installed `docs`
group (that group is not in the default set). It was immediately restored with
`uv sync --all-extras --all-groups`, so `just docs-build` still works locally. No file
changed as a result.

## Known Stubs

None. Every artifact this plan produced is complete and exercised.

## Threat Flags

None. The plan's own `<threat_model>` rows are discharged as planned: T-46-SC (supply
chain) by the RESEARCH legitimacy audit plus `uv.lock`'s recorded hashes for the resolved
set; T-46-06 (banned-api `msg` disclosure) by the messages being static literals that
interpolate nothing; T-46-07 (a repudiable gate) by the two executed probes above. No new
security-relevant surface was introduced — this plan adds no network endpoint, no auth
path, and no schema.

## For Later Plans in This Phase

- The venv now has the whole async stack: `create_async_pool`, `close_async_pool`,
  `AsyncPool`, `AsyncConnection`, `AsyncCursor`, `AsyncRecordBatchReader`, plus anyio and
  trio. RESEARCH's findings, read from the 1.6.1 wheel, can now be re-verified against the
  installed package rather than a downloaded archive.
- TID251 is live. Any module-level `import anyio` or `import asyncio` added under
  `src/semolina/` from here on fails `prek` and CI. Poolhouse imports must go inside
  function bodies anyway (Pitfall 3), so this and the lazy-import contract push the same
  way.
- `tests/unit/test_async_packaging.py`'s child-interpreter probe will catch a module-level
  `from adbc_poolhouse import create_async_pool` the moment one lands — it is the local
  mirror of the new CI step, so the failure surfaces in `just test` rather than only on CI.

## Self-Check: PASSED

- `tests/unit/test_async_packaging.py` — FOUND
- `pyproject.toml` — FOUND (async extra, TID select, banned-api, per-file-ignores all
  present and machine-verified)
- `.github/workflows/ci.yml` — FOUND (anyio step yaml-parsed)
- Commit `e0b3805` — FOUND
- Commit `71f3393` — FOUND
- Commit `ac2397d` — FOUND
- `src/semolina/_tid_probe.py` — correctly ABSENT
- `tests/unit/_tid_scope_probe.py` — correctly ABSENT
