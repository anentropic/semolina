---
phase: 08-integration-testing
investigation: custom-env-file-path-override
date: 2026-02-17
status: complete
---

# Investigation: Custom .env File Path Override for Credential Loader

## Gap Summary

From 08-UAT.md Test #2:
- **Expected:** Credentials can be loaded from a custom .env file path, not just default .env in cwd
- **Current:** Hardcoded to `.env` in current working directory
- **Use Cases:** CI/CD pipelines, multiple projects in same workspace, non-standard directory structures

---

## Current Implementation Analysis

### File: `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/testing/credentials.py`

**Current Behavior:**

1. **SnowflakeCredentials** (lines 49-54):
   ```python
   model_config = SettingsConfigDict(
       env_prefix="SNOWFLAKE_",
       env_file=".env",                    # HARDCODED
       env_file_encoding="utf-8",
       extra="ignore",
   )
   ```

2. **DatabricksCredentials** (lines 131-136):
   ```python
   model_config = SettingsConfigDict(
       env_prefix="DATABRICKS_",
       env_file=".env",                    # HARDCODED
       env_file_encoding="utf-8",
       extra="ignore",
   )
   ```

3. **Load Method Pattern** (lines 63-110, 144-190):
   - Calls `cls()` directly with no arguments
   - pydantic-settings automatically loads from hardcoded `.env` path
   - Falls back to config files only on exception

### Limitations

1. **No way to override .env path at runtime**
2. **No environment variable to specify custom path**
3. **No constructor argument to inject path**
4. **Only option: modify model_config (requires code change)**

---

## Pydantic-Settings Capabilities

### 1. `_env_file` Parameter (Approach #1)

**Supported:** YES — Available in pydantic-settings 2.7.0+

**How it works:**
```python
# BaseSettings accepts _env_file keyword argument at instantiation
creds = SnowflakeCredentials(_env_file="path/to/custom.env")
```

**Advantages:**
- Direct, explicit, clean API
- Single parameter for custom path
- Works with all versions of pydantic-settings 2.x

**Limitations:**
- Still loads from hardcoded path first, then tries custom path
- Requires passing parameter to `cls()` call

**Reference:** [Settings Management - Pydantic Validation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### 2. Environment Variable Control (Approach #2)

**Supported:** YES — Indirect via settings_customise_sources

**Pattern:**
- Read `ENV_FILE_PATH` environment variable
- Use `settings_customise_sources` to build custom DotEnvSettingsSource with runtime path
- Priority: env var → CLI arg → default

**Advantages:**
- No code changes needed when env var set
- CI/CD friendly (set in pipeline)
- Works in multiple parallel test workers (each can have own path)

**Limitations:**
- More complex implementation
- Requires `settings_customise_sources` override

**Reference:** [Override default file in Yaml/Toml/Json ConfigSettingsSource at runtime · Issue #259 · pydantic/pydantic-settings](https://github.com/pydantic/pydantic-settings/issues/259)

### 3. Factory Function Approach (Approach #3)

**Supported:** YES — Custom wrapper around BaseSettings

**Pattern:**
```python
@classmethod
def load(cls, env_file: str | None = None) -> "SnowflakeCredentials":
    env_file = env_file or os.getenv("CUBANO_ENV_FILE", ".env")
    return cls(_env_file=env_file)
```

**Advantages:**
- Explicit control at call site
- Backward compatible (env_file parameter is optional)
- Can combine with environment variable fallback
- Simple to understand and maintain

**Limitations:**
- Still need to modify .load() classmethod

---

## Investigation Answers

### Question 1: How does pydantic-settings load .env files? Can we inject a custom path?

**Answer:** YES. pydantic-settings uses `DotEnvSettingsSource` which:
1. Reads env_file path from SettingsConfigDict
2. Supports `_env_file` parameter at instantiation to override
3. Can be customized via `settings_customise_sources` classmethod

Current code doesn't use this capability.

### Question 2: Would this require changes to BaseSettings configuration or wrapper functions?

**Answer:** BOTH. Two options:

**Option A (Simple):** Modify `load()` classmethod
- Add optional parameter: `load(cls, env_file: str | None = None)`
- Pass to BaseSettings: `cls(_env_file=env_file or ".env")`
- Changes: 2 lines per credential class

**Option B (Flexible):** Implement settings_customise_sources
- Read ENV_FILE_PATH env var
- Build custom DotEnvSettingsSource at runtime
- Changes: ~15-20 lines per credential class

### Question 3: Should the custom path come from an environment variable, CLI argument, or both?

**Answer:** BOTH for maximum flexibility:

1. **Environment Variable** (highest priority): `CUBANO_ENV_FILE`
   - Set in CI/CD pipelines without code changes
   - Set in shell for local multi-project workflows

2. **Function Parameter** (second priority): `SnowflakeCredentials.load(env_file="/path")`
   - Explicit per-call override
   - Useful in tests, scripts

3. **Default** (lowest priority): `.env` in current directory
   - Backward compatible with existing usage
   - Works for simple single-project setups

### Question 4: Are there other credential use cases (not just tests) that would benefit from this?

**Answer:** YES, multiple:

1. **Local Development:**
   - Multiple projects in same directory
   - Switch between dev/staging/prod .env files
   - Example: `CUBANO_ENV_FILE=.env.staging pytest`

2. **CI/CD Pipelines:**
   - Different .env file per environment
   - Non-standard directory layout (secrets in different location)
   - Example: GitHub Actions runner with secrets in `/etc/cubano/.env`

3. **Testing:**
   - Test fixture with custom .env containing test credentials
   - Test verification of error handling with missing credentials
   - Parallel workers with isolated credential files per worker

4. **Production Scripts:**
   - Deploy scripts loading credentials from secure vault location
   - Containerized apps where .env is mounted at non-standard path
   - Example: Docker: `CUBANO_ENV_FILE=/secrets/.env python script.py`

---

## Recommended Solution Approach

### Primary Recommendation: Hybrid Approach

Implement both mechanisms for maximum flexibility:

1. **Environment Variable**: `CUBANO_ENV_FILE`
   - Highest priority (override everything)
   - Set once in CI/CD or shell, no code changes needed
   - Perfect for containerized deployments

2. **Function Parameter**: `env_file` argument to `.load()`
   - Second priority
   - Explicit per-call override
   - Useful for testing and local workflows

3. **Default**: `.env`
   - Lowest priority
   - Backward compatible
   - Requires no action for existing code

### Implementation Strategy

**File:** `src/cubano/testing/credentials.py`

**Changes per credential class (SnowflakeCredentials, DatabricksCredentials):**

1. Modify `load()` classmethod signature:
   ```python
   @classmethod
   def load(cls, env_file: str | None = None) -> "SnowflakeCredentials":
   ```

2. Logic for path resolution:
   ```python
   # Priority: env var > param > default
   env_file_path = env_file or os.getenv("CUBANO_ENV_FILE", ".env")
   ```

3. Pass to BaseSettings:
   ```python
   try:
       return cls(_env_file=env_file_path)
   except Exception:
       # Continue to config file fallback...
   ```

**Impact:**
- ~5-10 lines changed per credential class
- Fully backward compatible (env_file parameter optional)
- No breaking changes to existing fixtures
- Additional `import os` needed

### Alternative: settings_customise_sources (Advanced)

If more sophisticated control needed (e.g., dynamic precedence):

1. Override `settings_customise_sources` classmethod
2. Build `DotEnvSettingsSource` with runtime path
3. Allows environment variable to completely replace .env file

**When to use:** When you need fine-grained control over source ordering. Current simpler approach should suffice.

---

## Verification Checklist

Once implemented, verify:

- [ ] `.load()` accepts optional `env_file` parameter
- [ ] `CUBANO_ENV_FILE` environment variable is respected
- [ ] Custom path takes precedence over default
- [ ] Backward compatible: `.load()` with no args still works
- [ ] Error messages clear if custom path doesn't exist
- [ ] Works in parallel test execution (each worker can use different path)
- [ ] All quality gates pass:
  - [ ] `uv run basedpyright` (no errors)
  - [ ] `uv run ruff check` (no violations)
  - [ ] `uv run pytest` (all tests pass)
- [ ] Documentation updated with new usage examples

---

## Related Files

**Files to update:**
- `/Users/paul/Documents/Dev/Personal/cubano/src/cubano/testing/credentials.py` (main implementation)
- `/Users/paul/Documents/Dev/Personal/cubano/tests/conftest.py` (document usage in fixtures if needed)

**Files not affected:**
- Integration tests automatically inherit this capability
- No changes needed to .cubano.toml or ~/.config/cubano/config.toml fallback chain

---

## Sources & References

1. [Settings Management - Pydantic Validation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
2. [Pydantic Settings API Documentation](https://docs.pydantic.dev/latest/api/pydantic_settings/)
3. [Override default file in Yaml/Toml/Json ConfigSettingsSource at runtime · Issue #259](https://github.com/pydantic/pydantic-settings/issues/259)
4. [BaseSettings source: use runtime arguments in settings sources · Discussion #4170](https://github.com/pydantic/pydantic/discussions/4170)
