---
phase: 08-integration-testing
plan: "05"
subsystem: testing/credentials
tags: [credentials, env-file, configuration, backward-compatibility]
dependency_graph:
  requires: []
  provides: [custom-env-file-support, cubano-env-file-var]
  affects: [src/cubano/testing/credentials.py]
tech_stack:
  added: []
  patterns: [priority-chain, environment-variable-override]
key_files:
  created: []
  modified:
    - src/cubano/testing/credentials.py
decisions:
  - "Use _env_file parameter at cls() instantiation (not model_config) for runtime env_file override"
  - "CUBANO_ENV_FILE env var > env_file parameter > .env default priority chain"
  - "Minimal implementation: 3 lines added per class (os.getenv + or chain)"
metrics:
  duration: "1 min"
  completed: "2026-02-17"
  tasks: 1
  files_modified: 1
requirements-completed: [INT-06]
---

# Phase 8 Plan 05: Custom env_file Support Summary

Custom env_file parameter added to SnowflakeCredentials.load() and DatabricksCredentials.load() with CUBANO_ENV_FILE environment variable priority chain.

## What Was Built

Both credential loader classes (`SnowflakeCredentials` and `DatabricksCredentials`) now accept an optional `env_file` parameter, with support for the `CUBANO_ENV_FILE` environment variable as a highest-priority override.

**Priority chain (highest to lowest):**
1. `CUBANO_ENV_FILE` environment variable
2. `env_file` parameter passed to `load()`
3. Default `".env"` in current working directory

## Changes Made

### `src/cubano/testing/credentials.py`

- Added `import os` at top of file
- Updated `SnowflakeCredentials.load()`:
  - Signature: `def load(cls, env_file: str | None = None) -> "SnowflakeCredentials"`
  - Priority chain via: `env_file_to_use = os.getenv("CUBANO_ENV_FILE") or env_file or ".env"`
  - Pass to BaseSettings: `cls(_env_file=env_file_to_use)` (runtime override of env_file)
  - Updated docstring with priority chain documentation
- Updated `DatabricksCredentials.load()`:
  - Identical changes applied

## Verification Results

All three usage patterns verified:

| Test | Pattern | Result |
|------|---------|--------|
| 1 | Default `.load()` — no parameters | Loads from `.env` by default, backward compatible |
| 2 | `.load(env_file='/tmp/custom.env')` | Loads from custom path |
| 3 | `CUBANO_ENV_FILE=/tmp/override.env` + `.load(env_file='/tmp/other.env')` | CUBANO_ENV_FILE wins |

Quality gates:
- `uv run basedpyright`: 0 errors, 0 warnings, 0 notes
- `uv run ruff check`: All checks passed

## Deviations from Plan

None - plan executed exactly as written.

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add custom env_file parameter to credential loaders | d7d5116 | src/cubano/testing/credentials.py |

## Self-Check: PASSED
