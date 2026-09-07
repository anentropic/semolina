---
phase: 51-ship-safely-release-ci-gates
status: executed
requirements: [REL-01, REL-02, REL-03, REL-04, REL-05, REL-06, REL-07, REL-08]
date: 2026-09-07
---

# Phase 51 Summary: Ship Safely — Release & CI Gates

Executed as five commits rather than the four plans the roadmap listed; the scope-fence work
split into the test-first pair CLAUDE.md requires.

| Commit | Covers | Roadmap plan |
|--------|--------|--------------|
| `113d26b` test(scope-fence) | REL-06 (failing tests) | 51-04 |
| `fd27976` fix(scope-fence) | REL-06 (fix) | 51-04 |
| `f9c02be` ci(release) | REL-01, REL-02 | 51-01 |
| `61801f8` ci | REL-03, REL-04, REL-05 (CI half), REL-08 (matrix) | 51-02 |
| `be6e156` chore(dev) | REL-05 (local half), REL-07 | 51-03 |

## What each requirement got

**REL-01 — tag matches version.** A `version-gate` job runs before anything is built and
compares `github.ref_name` with `project.version` as PEP 440 versions, so `v0.7.0-rc1`
matches `0.7.0rc1` (confirmed: `Version("0.7.0-rc1") == Version("0.7.0rc1")` is `True`).
Exercised against the current tree before committing: `v0.6.0` exits 0, `v0.7.0` exits 1
naming both values, `vbogus` exits 1 as an invalid PEP 440 version.

**REL-02 — publish waits on CI.** `ci.yml` gained a `workflow_call` trigger and `release.yml`
now calls it, with `publish` in its `needs`. This runs the suite against the tagged commit
itself, which nothing did before: `ci.yml` carries `tags-ignore: "**"`. `validate` also now
asserts the built wheel reports the tagged version rather than printing it.

**REL-03 — PRs and coverage.** Added the `pull_request` trigger; `push` narrowed to `main`
so PR branches are not built twice. Making the coverage comment reachable exposed two
defects in it that were invisible while it was dead code: `pytest-coverage-path` takes
pytest-cov's *text* output, not the XML that was passed, and under a matrix it would post one
comment per interpreter. Now `pytest-xml-coverage-path`, gated to the 3.11 leg, and
`continue-on-error` because fork tokens are read-only. Coverage XML is uploaded per
interpreter, and `[tool.coverage.report] fail_under = 93` turns the measurement into a gate.

**REL-04 — docs gate.** A `docs` job runs `sphinx-build -W docs/src docs/_build` on every
push and PR, the same command `docs.yml` and the justfile use.

**REL-05 — `just test` parity.** Both halves moved toward each other. `just test` now runs
`uv sync --locked --dev --extra all` first, which is what every CI test job syncs; without it
about fifty test files `importorskip` and the recipe reports green over a much smaller suite.
CI dropped `-m duckdb` from the jaffle-shop step, which had hidden the three
model-translation tests in `src/semolina_jaffle_shop/` from CI while `just test` ran them.
Verified unfiltered: 16 passed, 15 skipped, the Snowflake tests skipping themselves on absent
credentials exactly as they do locally. The recipe also moved from `pushd`/`popd` to
`cd X && …`, since just runs each line under `sh`.

**REL-06 — scope fence on a shallow clone.** `test_the_default_base_ref_resolves_here`
asserted unconditionally, so any `--depth 1` checkout turned the suite red — the outcome the
module's own `_unrunnable` policy exists to prevent. It now routes through `_unrunnable` and
reads `_resolve_base_ref()`, so it checks the ref the fence will actually diff against.
Proven on a real `git clone --depth 1` of this repository: with `CI` unset, 10 passed and 2
skipped with the unresolvable ref named in the message; with `CI=true`, both the fence and
the premise check fail loudly. This was the one test failing at review time.

**REL-07 — ruff pin.** Pre-commit sat at `v0.9.6` against a locked `0.15.20`, with CI linting
via `uv run ruff`. Pinned to the locked version with a comment to keep them equal. `ruff
check` and `ruff format --check` pass at 0.15.20.

**REL-08 — matrix, and a finding that was not a defect.** The matrix now runs 3.11, 3.12,
3.13 and 3.14; the middle two were never exercised despite `uv.lock` carrying a distinct
resolution marker per minor.

The `.python-version` half was investigated and **no change was made**, because the evidence
did not support one. The review observed `.python-version = 3.14` resolving to 3.14.0rc2, on
which the locked pydantic raises `TypeError: _eval_type() got an unexpected keyword argument
'prefer_fwd_module'` at import. That was the review sandbox running uv 0.8.17, whose bundled
Python index predates the stable 3.14 release — `uv python install 3.14.0` there still
resolves to rc2. This project already requires newer uv (`uv_build>=0.9.18`, and the
`uv-pre-commit` hook pinned to 0.9.18), where `3.14` resolves to the stable build. Changing
the pin on that evidence would have been treating a stale toolchain as a repository defect.
The floor is now stated in MAINTAINER.md instead, with the symptom named so the next person
who hits it recognises it.

## What is not yet proven

Three claims cannot be closed from this branch and close themselves on first use:

1. **The `workflow_call` from `release.yml`** has never run. Its shape is validated (YAML
   parses, job graph resolves, `uses: ./.github/workflows/ci.yml` with `publish` needing it)
   but the first real proof is the `v0.7.0` tag in Phase 57. This is expected: `release.yml`
   has never executed at all — `0.3.0`, `0.4.0` and `0.6.0` were published outside it, which
   is why the repository carries no tags.
2. **The coverage comment on a PR.** Reachable for the first time, and rewired on the way,
   but no PR has exercised it. It is `continue-on-error`, so a wrong guess costs a missing
   comment rather than a red run.
3. **`just test` end to end** was not run here: `just` is not installed in the review
   sandbox, and the recipe's `uv sync` targets a `.venv` that this sandbox's old uv builds on
   3.14.0rc2. The commands it runs were each executed directly instead, against a 3.11
   environment.

## Gates at phase close

Run on the final tree:

| Gate | Result |
|------|--------|
| `ruff check` | All checks passed |
| `ruff format --check` | 109 files already formatted |
| `basedpyright` | 0 errors, 0 warnings, 0 notes |
| `pytest` (3.11, `-n auto`, with coverage) | 1740 passed, 16 skipped, 2 xfailed |
| Coverage | 96.44%, above the new 93% floor |
| jaffle-shop (unfiltered) | 16 passed, 15 skipped |
| `sphinx-build -W` | clean |

The suite is 1740 passing where the review measured 1736 passing and 1 failing: the four new
tests are the two scope-fence behaviour tests plus their two counterparts, and the failure is
gone.

One note on the basedpyright run. It reported 22 unresolved-import errors mid-phase, all for
optional-extra packages. That was a local `.venv` left partly synced by the review session,
not a regression: the same errors reproduced on a stashed, unmodified tree, and a clean
`uv sync --locked --dev --extra all` returned it to 0 errors.

## Next

Phase 52 (Core Object Semantics). Nothing in Phase 51 blocks it. Decision D1 (model
inheritance) gates plan 52-06 only, so the other five plans can start without it.
