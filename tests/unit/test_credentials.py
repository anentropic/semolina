"""
Unit tests for custom .env file path support in credential loaders.

Tests verify the three-tier priority chain for env_file resolution:
1. CUBANO_ENV_FILE environment variable (highest priority)
2. env_file parameter passed to .load()
3. Default ".env" in the current working directory

All tests are marked @pytest.mark.unit and run without warehouse credentials.
"""

from pathlib import Path

import pytest

from cubano.testing.credentials import (
    CredentialError,
    DatabricksCredentials,
    SnowflakeCredentials,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _create_credentials_env_file(tmpdir: Path, filename: str, **vars: str) -> Path:
    """
    Create .env file with given variables in tmpdir.

    Args:
        tmpdir: Temporary directory to write the file into
        filename: Name of the .env file to create
        **vars: Key=value pairs to write into the file

    Returns:
        Path to the created .env file
    """
    env_file = tmpdir / filename
    content = "\n".join(f"{key}={value}" for key, value in vars.items())
    env_file.write_text(content)
    return env_file


# ---------------------------------------------------------------------------
# SnowflakeCredentials tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snowflake_default_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that SnowflakeCredentials.load() reads from the default .env file.

    Verifies backward compatibility: calling load() without env_file parameter
    picks up .env from the current working directory.
    """
    # Arrange: create .env in tmp_path and change cwd to it
    _create_credentials_env_file(
        tmp_path,
        ".env",
        SNOWFLAKE_ACCOUNT="default_account",
        SNOWFLAKE_USER="default_user",
        SNOWFLAKE_PASSWORD="default_pass",
        SNOWFLAKE_WAREHOUSE="default_wh",
        SNOWFLAKE_DATABASE="default_db",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
    # Remove any leaked SNOWFLAKE_* env vars from the environment
    for key in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act
    creds = SnowflakeCredentials.load()

    # Assert
    assert creds.account == "default_account"
    assert creds.user == "default_user"
    assert creds.warehouse == "default_wh"
    assert creds.database == "default_db"


@pytest.mark.unit
def test_snowflake_custom_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that SnowflakeCredentials.load(env_file=...) loads from the specified path.

    Verifies that a custom env_file parameter takes precedence over the default .env
    in the working directory when CUBANO_ENV_FILE is not set.
    """
    # Arrange: create a default .env and a custom env file
    _create_credentials_env_file(
        tmp_path,
        ".env",
        SNOWFLAKE_ACCOUNT="default_account",
        SNOWFLAKE_USER="default_user",
        SNOWFLAKE_PASSWORD="default_pass",
        SNOWFLAKE_WAREHOUSE="default_wh",
        SNOWFLAKE_DATABASE="default_db",
    )
    custom_env = _create_credentials_env_file(
        tmp_path,
        "custom.env",
        SNOWFLAKE_ACCOUNT="custom_account",
        SNOWFLAKE_USER="custom_user",
        SNOWFLAKE_PASSWORD="custom_pass",
        SNOWFLAKE_WAREHOUSE="custom_wh",
        SNOWFLAKE_DATABASE="custom_db",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
    for key in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act: load with custom env_file path
    creds = SnowflakeCredentials.load(env_file=str(custom_env))

    # Assert: custom path values are loaded, not defaults
    assert creds.account == "custom_account"
    assert creds.user == "custom_user"
    assert creds.warehouse == "custom_wh"
    assert creds.database == "custom_db"


@pytest.mark.unit
def test_cubano_env_file_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that CUBANO_ENV_FILE has highest priority, overriding the env_file parameter.

    Verifies the priority chain: CUBANO_ENV_FILE > env_file parameter > default .env.
    When CUBANO_ENV_FILE is set it must override the env_file parameter.
    """
    # Arrange: create two separate env files
    default_env = _create_credentials_env_file(
        tmp_path,
        "default.env",
        SNOWFLAKE_ACCOUNT="default_account",
        SNOWFLAKE_USER="default_user",
        SNOWFLAKE_PASSWORD="default_pass",
        SNOWFLAKE_WAREHOUSE="default_wh",
        SNOWFLAKE_DATABASE="default_db",
    )
    cubano_env = _create_credentials_env_file(
        tmp_path,
        "cubano.env",
        SNOWFLAKE_ACCOUNT="cubano_account",
        SNOWFLAKE_USER="cubano_user",
        SNOWFLAKE_PASSWORD="cubano_pass",
        SNOWFLAKE_WAREHOUSE="cubano_wh",
        SNOWFLAKE_DATABASE="cubano_db",
    )
    monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
    for key in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act: set CUBANO_ENV_FILE and pass a different path as env_file parameter
    monkeypatch.setenv("CUBANO_ENV_FILE", str(cubano_env))
    creds = SnowflakeCredentials.load(env_file=str(default_env))

    # Assert: CUBANO_ENV_FILE values win, not the env_file parameter
    assert creds.account == "cubano_account"
    assert creds.warehouse == "cubano_wh"
    assert creds.database == "cubano_db"


@pytest.mark.unit
def test_cubano_env_file_missing_raises_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that CredentialError is raised when CUBANO_ENV_FILE points to a missing file.

    When CUBANO_ENV_FILE is set to a non-existent path and no credential env vars
    or config files are available, load() must raise CredentialError.
    """
    # Arrange: no .env file, no env vars, CUBANO_ENV_FILE points to missing file
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUBANO_ENV_FILE", str(tmp_path / "nonexistent.env"))
    for key in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act + Assert: CredentialError raised because no source provides credentials
    with pytest.raises(CredentialError):
        SnowflakeCredentials.load()


# ---------------------------------------------------------------------------
# DatabricksCredentials tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_databricks_custom_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that DatabricksCredentials.load(env_file=...) loads from the specified path.

    Verifies that the env_file parameter works correctly for Databricks credentials.
    """
    # Arrange: create custom env file with Databricks credentials
    custom_env = _create_credentials_env_file(
        tmp_path,
        "databricks.env",
        DATABRICKS_SERVER_HOSTNAME="my-workspace.azuredatabricks.net",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/abc123",
        DATABRICKS_ACCESS_TOKEN="dapi_token_123",
        DATABRICKS_CATALOG="my_catalog",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
    for key in [
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_ACCESS_TOKEN",
        "DATABRICKS_CATALOG",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act
    creds = DatabricksCredentials.load(env_file=str(custom_env))

    # Assert
    assert creds.server_hostname == "my-workspace.azuredatabricks.net"
    assert creds.http_path == "/sql/1.0/warehouses/abc123"
    assert creds.catalog == "my_catalog"


@pytest.mark.unit
def test_databricks_cubano_env_file_priority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that CUBANO_ENV_FILE has highest priority for DatabricksCredentials.

    Verifies that CUBANO_ENV_FILE overrides the env_file parameter for Databricks,
    consistent with the same priority chain as SnowflakeCredentials.
    """
    # Arrange: create two separate env files
    param_env = _create_credentials_env_file(
        tmp_path,
        "param.env",
        DATABRICKS_SERVER_HOSTNAME="param-host.azuredatabricks.net",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/param",
        DATABRICKS_ACCESS_TOKEN="dapi_param_token",
    )
    cubano_env = _create_credentials_env_file(
        tmp_path,
        "cubano.env",
        DATABRICKS_SERVER_HOSTNAME="cubano-host.azuredatabricks.net",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/cubano",
        DATABRICKS_ACCESS_TOKEN="dapi_cubano_token",
    )
    monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
    for key in [
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_ACCESS_TOKEN",
        "DATABRICKS_CATALOG",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act: set CUBANO_ENV_FILE and pass a different path as env_file parameter
    monkeypatch.setenv("CUBANO_ENV_FILE", str(cubano_env))
    creds = DatabricksCredentials.load(env_file=str(param_env))

    # Assert: CUBANO_ENV_FILE values win
    assert creds.server_hostname == "cubano-host.azuredatabricks.net"
    assert creds.http_path == "/sql/1.0/warehouses/cubano"


@pytest.mark.unit
def test_backward_compatibility(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that SnowflakeCredentials.load() still reads from environment variables.

    Verifies that existing code not using env_file parameter continues to work
    when credentials are provided via environment variables only (no .env file).
    """
    # Arrange: set environment variables, no .env file exists in cwd
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CUBANO_ENV_FILE", raising=False)
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "env_account")
    monkeypatch.setenv("SNOWFLAKE_USER", "env_user")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "env_pass")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "env_wh")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "env_db")

    # Act: no env_file parameter — should still load from environment variables
    creds = SnowflakeCredentials.load()

    # Assert: environment variable values are used
    assert creds.account == "env_account"
    assert creds.user == "env_user"
    assert creds.warehouse == "env_wh"
    assert creds.database == "env_db"


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
    for key in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Act: override role at load time
    creds = SnowflakeCredentials.load(role="ANALYST")

    # Assert
    assert creds.role == "ANALYST"


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
    for key in [
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_ROLE",
    ]:
        monkeypatch.delenv(key, raising=False)

    creds = SnowflakeCredentials.load()

    assert creds.role is None
