---
phase: 27
slug: toml-configuration-real-pools
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/unit/test_config.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/unit/test_config.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 01 | 1 | CONF-01 | unit | `uv run pytest tests/unit/test_config.py::TestTomlParsing -x` | ❌ W0 | ⬜ pending |
| 27-01-02 | 01 | 1 | CONF-01 | unit | `uv run pytest tests/unit/test_config.py::TestConfigDispatch -x` | ❌ W0 | ⬜ pending |
| 27-01-03 | 01 | 1 | CONF-02 | unit | `uv run pytest tests/unit/test_config.py::TestSnowflakeConfig -x` | ❌ W0 | ⬜ pending |
| 27-01-04 | 01 | 1 | CONF-02 | unit | `uv run pytest tests/unit/test_config.py::TestDatabricksConfig -x` | ❌ W0 | ⬜ pending |
| 27-01-05 | 01 | 1 | CONF-03 | unit | `uv run pytest tests/unit/test_config.py::TestPoolFromConfig -x` | ❌ W0 | ⬜ pending |
| 27-01-06 | 01 | 1 | - | unit | `uv run pytest tests/unit/test_config.py::TestConfigErrors -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_config.py` — new file covering CONF-01, CONF-02, CONF-03
- [ ] Mock `adbc_poolhouse.create_pool` to avoid requiring real ADBC drivers
- [ ] TOML fixtures via `tempfile` module

*Framework install: not needed — pytest already configured*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real pool creation with Snowflake credentials | CONF-03 | Requires live Snowflake account | Set up `.semolina.toml` with real creds, run `pool_from_config()` |
| Real pool creation with Databricks credentials | CONF-03 | Requires live Databricks workspace | Set up `.semolina.toml` with real creds, run `pool_from_config()` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
