---
phase: 27-toml-configuration-real-pools
verified: 2026-03-17T00:00:00Z
status: passed
score: 8/8 must-haves verified
re_verification: false
---

# Phase 27: TOML Configuration & Real Pools Verification Report

**Phase Goal:** Users can define connections in `.semolina.toml` and create pools from config without manual pool construction
**Verified:** 2026-03-17
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                              | Status     | Evidence                                                                                   |
|----|------------------------------------------------------------------------------------|------------|-------------------------------------------------------------------------------------------|
| 1  | `pool_from_config()` reads a TOML file and returns a `(pool, Dialect)` tuple       | VERIFIED   | `config.py` lines 60-87: opens TOML, dispatches via `_CONFIG_MAP`, returns `(pool, dialect)` |
| 2  | `type` field in TOML connection section determines which adbc-poolhouse config class is used | VERIFIED   | `_CONFIG_MAP` dict at line 22-25 maps `"snowflake"` to `SnowflakeConfig` and `"databricks"` to `DatabricksConfig`; `TestConfigDispatch` tests confirm dispatch |
| 3  | Missing config file raises `FileNotFoundError`                                     | VERIFIED   | `path.open("rb")` at line 61 raises natively; `test_missing_file_raises_file_not_found` passes |
| 4  | Missing connection section raises `KeyError` with available connections listed     | VERIFIED   | Lines 65-70 raise `KeyError` with available list; `test_missing_connection_shows_available` passes |
| 5  | Missing or unsupported `type` field raises `ValueError` with supported types listed | VERIFIED   | Lines 74-82 raise `ValueError` for missing and unsupported type; `test_unsupported_type_shows_supported` passes |
| 6  | `pool_from_config` is importable from top-level `semolina` package                | VERIFIED   | `__init__.py` line 8: `from .config import pool_from_config`; in `__all__` at line 38 |
| 7  | `.semolina.toml.example` shows the new `[connections.name]` format with `type` field | VERIFIED   | Example has `[connections.default]` with `type = "snowflake"` and commented Databricks section; old fields `server_hostname`/`access_token` absent |
| 8  | `registry.reset()` properly closes adbc-poolhouse pools via `close_pool()`        | VERIFIED   | `registry.py` lines 154-159: `hasattr(pool, "_adbc_source")` guard with lazy `close_pool` import; `test_reset_uses_close_pool_for_adbc_pools` passes |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/semolina/config.py` | `pool_from_config()` factory and `_CONFIG_MAP` dispatch; exports `pool_from_config` | VERIFIED | 88 lines; top-level `from adbc_poolhouse import`; `_CONFIG_MAP`; `pool_from_config` function fully implemented |
| `tests/unit/test_config.py` | Unit tests for config module with mocked `create_pool`; min 80 lines | VERIFIED | 297 lines; 15 tests across `TestConfigDispatch` (3), `TestPoolFromConfig` (6), `TestConfigErrors` (6); all 15 pass |
| `pyproject.toml` | `adbc-poolhouse` as core dependency | VERIFIED | Line 11: `"adbc-poolhouse>=1.2.0"` in `[project] dependencies`; line 34: `"adbc-poolhouse[snowflake]"` in snowflake extra |
| `src/semolina/__init__.py` | `pool_from_config` in public API exports | VERIFIED | Import at line 8; `"pool_from_config"` in `__all__` at line 38 |
| `.semolina.toml.example` | Example TOML with `[connections.default]` format | VERIFIED | Contains `[connections.default]`, `type = "snowflake"`, correct adbc-poolhouse field names; old `server_hostname`/`access_token` absent |
| `src/semolina/registry.py` | Improved `reset()` using `close_pool` for adbc-poolhouse pools | VERIFIED | Lines 144-161: `hasattr(_adbc_source)` check, lazy `close_pool` import, fallback to `pool.close()` for non-ADBC pools |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/semolina/config.py` | `adbc_poolhouse` | top-level `from adbc_poolhouse import SnowflakeConfig, DatabricksConfig, create_pool` | WIRED | Lines 14-18: top-level import, not lazy |
| `src/semolina/config.py` | `src/semolina/dialect.py` | `from .dialect import Dialect` | WIRED | Line 20 |
| `src/semolina/__init__.py` | `src/semolina/config.py` | `from .config import pool_from_config` | WIRED | Line 8 |
| `src/semolina/registry.py` | `adbc_poolhouse` | `close_pool` lazy import in `reset()` | WIRED | Lines 155-156: `from adbc_poolhouse import close_pool` inside `hasattr` branch |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CONF-01 | 27-01 | `.semolina.toml` connection sections have a backend sub-section (snowflake/databricks) determining config class | SATISFIED | `_CONFIG_MAP` dispatch in `config.py`; `[connections.NAME]` format with `type` field in `.semolina.toml.example` |
| CONF-02 | 27-01 | `.semolina.toml` sections load into adbc-poolhouse config classes via TomlSettingsSource | SATISFIED | `config_cls(**section)` at line 85 passes TOML fields as kwargs to adbc-poolhouse config class; `test_toml_fields_passed_as_kwargs` confirms correct kwargs |
| CONF-03 | 27-01, 27-02 | User can create a pool via `pool_from_config(connection="conn1")` with default `.semolina.toml` path | SATISFIED | `pool_from_config` callable from `semolina` public API; default `connection="default"` and `config_path=".semolina.toml"` parameters; `test_default_connection_name` and `test_named_connection` pass |

No orphaned requirements: all three CONF-0x IDs assigned to Phase 27 in REQUIREMENTS.md are accounted for across plans 27-01 and 27-02.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no empty implementations, no stub returns in any phase file.

### Human Verification Required

None. All truths are verifiable through code inspection and automated tests.

### Test Run Results

| Test Suite | Result | Count |
|------------|--------|-------|
| `tests/unit/test_config.py` | PASS | 15/15 |
| `tests/unit/test_registry.py` | PASS | 24/24 (includes new `test_reset_uses_close_pool_for_adbc_pools`) |
| `tests/unit/` (full suite, excluding pre-existing connector failures) | PASS | 740/740 |

**Pre-existing failures** (unrelated to this phase, present before phase 27):
- `tests/unit/test_databricks_engine.py` — requires `databricks-sql-connector` optional extra not installed
- `tests/unit/test_snowflake_engine.py` — requires `snowflake-connector-python` optional extra not installed

Both documented in 27-01-SUMMARY.md under "Issues Encountered."

### Quality Gates

| Gate | Result |
|------|--------|
| `uv run ruff check` (phase files) | PASS — no issues |
| `uv run ruff format --check` (phase files) | PASS — 4 files already formatted |
| `uv run basedpyright src/semolina/config.py src/semolina/registry.py src/semolina/__init__.py` | PASS — 0 errors, 0 warnings, 0 notes |

### Commit Verification

All four commits documented in summaries confirmed present in git log:

| Commit | Description |
|--------|-------------|
| `a1e76e0` | test(27-01): add failing tests for config module |
| `0dd6596` | feat(27-01): implement pool_from_config() with TOML config loading |
| `55e4ad5` | feat(27-02): export pool_from_config and update TOML example |
| `2a34c80` | feat(27-02): improve registry.reset() to use close_pool for ADBC pools |

---

## Phase Goal Assessment

The phase goal is fully achieved. Users can:

1. Define connections in `.semolina.toml` using `[connections.NAME]` sections with a `type` field
2. Call `pool_from_config(connection="name")` (or just `pool_from_config()` for the default) to obtain a `(pool, Dialect)` tuple ready for `register()`
3. No manual construction of `SnowflakeConfig` or `DatabricksConfig` objects is required

The implementation is substantive (not a stub), wired throughout the public API, tested with 15 dedicated tests, and all quality gates pass cleanly.

---

_Verified: 2026-03-17_
_Verifier: Claude (gsd-verifier)_
