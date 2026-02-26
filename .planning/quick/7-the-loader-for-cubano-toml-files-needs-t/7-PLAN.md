---
phase: quick-7
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/cubano/testing/credentials.py
  - tests/conftest.py
  - tests/test_credentials.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "SnowflakeCredentials.load(role='MY_ROLE') overrides the role field on the returned credentials"
    - "SnowflakeCredentials.load() with no role arg still uses whatever role comes from env/config (including None)"
    - "The snowflake_engine snapshot fixture passes role to SnowflakeEngine so the connector uses the right role"
    - "Unit tests cover role override in load() and confirm None is preserved when not specified"
    - "All quality gates pass: typecheck, lint, format, tests"
  artifacts:
    - path: "src/cubano/testing/credentials.py"
      provides: "SnowflakeCredentials.load() with role parameter"
      contains: "def load(cls, env_file: str | None = None, role: str | None = None)"
    - path: "tests/conftest.py"
      provides: "snowflake_engine fixture passing role kwarg to SnowflakeEngine"
      contains: "role=creds.role"
    - path: "tests/test_credentials.py"
      provides: "Unit tests for role override behaviour"
  key_links:
    - from: "tests/conftest.py (snowflake_engine)"
      to: "SnowflakeEngine(**connection_params)"
      via: "role=creds.role kwarg"
      pattern: "role=creds\\.role"
    - from: "SnowflakeCredentials.load(role=...)"
      to: "returned SnowflakeCredentials instance"
      via: "model_copy(update={'role': role}) when role is not None"
      pattern: "model_copy"
---

<objective>
Add a `role` override parameter to `SnowflakeCredentials.load()` and ensure the Snowflake connector
receives the role from credentials wherever `SnowflakeEngine` is constructed.

Purpose: Users with multiple Snowflake roles need to specify which role to activate when loading
credentials. The current `load()` signature has no way to override role at call time. Additionally,
the `snowflake_engine` snapshot fixture omits `role` when constructing `SnowflakeEngine`, which
means the role from `.cubano.toml` or env vars is silently dropped during snapshot recording.
Output: Updated `credentials.py`, `conftest.py`, and a new unit test covering role override.
</objective>

<execution_context>
@/Users/paul/.claude/get-shit-done/workflows/execute-plan.md
@/Users/paul/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@src/cubano/testing/credentials.py
@tests/conftest.py
@tests/test_credentials.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add role parameter to SnowflakeCredentials.load()</name>
  <files>src/cubano/testing/credentials.py</files>
  <action>
    Modify `SnowflakeCredentials.load()` to accept a `role: str | None = None` keyword argument.

    When `role` is not None, override the `role` field on the returned credentials object using
    `model_copy(update={"role": role})` AFTER loading from whichever source succeeded. This way
    all three loading paths (env vars, env file, config file) are covered by one override step.

    Updated signature:
    ```python
    @classmethod
    def load(cls, env_file: str | None = None, role: str | None = None) -> "SnowflakeCredentials":
    ```

    Updated docstring must document the `role` parameter:
    ```
    Args:
        env_file: Optional path to .env file. Overridden by CUBANO_ENV_FILE env var.
        role: Optional role override. When provided, replaces the role from env/config.
            Use when the caller knows which Snowflake role to activate (e.g., specific
            read-only role for tests). When None, role comes from SNOWFLAKE_ROLE env var
            or the [snowflake] config section (may itself be None).
    ```

    Apply the override at each successful return point (there are two: the pydantic-settings
    path at line ~94 and the config-file path at line ~110). The cleanest approach is to
    capture the result in a local variable `creds`, then return `creds.model_copy(update={"role": role})`
    when `role is not None` else return `creds` as-is.

    Refactor the method body so there is a single override application:

    ```python
    def _apply_role(creds: "SnowflakeCredentials") -> "SnowflakeCredentials":
        return creds.model_copy(update={"role": role}) if role is not None else creds
    ```

    Then wrap each return statement: `return _apply_role(cls(...))` and
    `return _apply_role(cls(**config["snowflake"]))`.

    Do NOT add a `role` parameter to `DatabricksCredentials.load()` — Databricks does not
    have an equivalent role concept in this codebase.
  </action>
  <verify>
    Run: uv run basedpyright src/cubano/testing/credentials.py
    Expected: 0 errors, 0 warnings.

    Run: uv run ruff check src/cubano/testing/credentials.py
    Expected: All checks passed.
  </verify>
  <done>
    `SnowflakeCredentials.load(role="ANALYST")` returns credentials with `role == "ANALYST"` regardless
    of what SNOWFLAKE_ROLE env var or config file contains. `load()` with no role preserves existing
    behaviour. Typecheck and lint pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Fix snowflake_engine fixture and add unit tests</name>
  <files>tests/conftest.py, tests/test_credentials.py</files>
  <action>
    ### conftest.py — fix snowflake_engine fixture

    In the `snowflake_engine` fixture (around line 366-372), the `SnowflakeEngine` constructor call
    currently omits `role`. Add it:

    ```python
    engine = _SnowflakeEngine(
        account=creds.account,
        user=creds.user,
        password=creds.password.get_secret_value(),
        warehouse=creds.warehouse,
        database=creds.database,
        role=creds.role,          # add this line
    )
    ```

    Note: `snowflake.connector.connect()` accepts `role=None` without error (it simply doesn't set
    a role, equivalent to the current behaviour). So passing `role=creds.role` is safe whether
    `creds.role` is a string or None.

    ### test_credentials.py — add role override tests

    Add two new unit tests to the `# SnowflakeCredentials tests` section:

    **Test 1 — role override via load(role=...):**
    ```python
    @pytest.mark.unit
    def test_snowflake_load_role_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Test that load(role=...) overrides the role from the env/config source.

        When a caller passes role='ANALYST', the returned credentials must have
        role='ANALYST' regardless of SNOWFLAKE_ROLE or config file contents.
        """
        # Arrange: env file without role (role will be None from env source)
        _create_credentials_env_file(
            tmp_path,
            ".env",
            SNOWFLAKE_ACCOUNT="acct",
            SNOWFLAKE_USER="user",
            SNOWFLAKE_PASSWORD="pass",
            SNOWFLAKE_WAREHOUSE="wh",
            SNOWFLAKE_DATABASE="db",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
        for key in ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                    "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_ROLE"]:
            monkeypatch.delenv(key, raising=False)

        # Act: override role at load time
        creds = SnowflakeCredentials.load(role="ANALYST")

        # Assert
        assert creds.role == "ANALYST"
    ```

    **Test 2 — no role arg preserves None:**
    ```python
    @pytest.mark.unit
    def test_snowflake_load_no_role_preserves_none(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Test that load() without role arg leaves role as None when not in env/config.

        Verifies backward compatibility: omitting role from load() and having no
        SNOWFLAKE_ROLE env var results in creds.role == None.
        """
        _create_credentials_env_file(
            tmp_path,
            ".env",
            SNOWFLAKE_ACCOUNT="acct",
            SNOWFLAKE_USER="user",
            SNOWFLAKE_PASSWORD="pass",
            SNOWFLAKE_WAREHOUSE="wh",
            SNOWFLAKE_DATABASE="db",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
        for key in ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                    "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_ROLE"]:
            monkeypatch.delenv(key, raising=False)

        creds = SnowflakeCredentials.load()

        assert creds.role is None
    ```

    Ensure the test file's import block already includes `SnowflakeCredentials` and
    `CredentialError` — do not duplicate imports.
  </action>
  <verify>
    Run: uv run --extra dev pytest tests/test_credentials.py -v
    Expected: All existing tests pass, both new tests pass.

    Run: uv run basedpyright tests/conftest.py tests/test_credentials.py
    Expected: 0 errors.

    Run: uv run ruff check tests/conftest.py tests/test_credentials.py
    Expected: All checks passed.
  </verify>
  <done>
    `snowflake_engine` fixture passes `role=creds.role` to `SnowflakeEngine`. Two new unit tests
    pass: role override returns correct role, no-role returns None. All existing credential tests
    still pass. Typecheck and lint clean.
  </done>
</task>

</tasks>

<verification>
After both tasks complete:

1. `uv run basedpyright` — 0 errors (strict mode)
2. `uv run ruff check` — 0 issues
3. `uv run ruff format --check` — all formatted
4. `uv run --extra dev pytest tests/test_credentials.py -v` — all tests pass including the two new ones
5. `uv run --extra dev pytest tests/ -v` — full test suite passes
</verification>

<success_criteria>
- `SnowflakeCredentials.load(role="MY_ROLE")` returns credentials with `role == "MY_ROLE"`
- `SnowflakeCredentials.load()` returns credentials with `role is None` when no SNOWFLAKE_ROLE env var
- `snowflake_engine` fixture in conftest.py passes `role=creds.role` to `SnowflakeEngine`
- All quality gates pass: typecheck (0 errors), lint (0 errors), format (clean), tests (all pass)
</success_criteria>

<output>
After completion, create `.planning/quick/7-the-loader-for-cubano-toml-files-needs-t/7-SUMMARY.md`
</output>
