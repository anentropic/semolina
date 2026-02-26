"""
Credential management for integration tests with fallback chain.

Supports loading credentials from:
1. Environment variables (SNOWFLAKE_* / DATABRICKS_*)
2. .env file in project root
3. Config files (.cubano.toml, ~/.config/cubano/config.toml)
4. CredentialError if all sources fail

Sensitive fields use SecretStr to prevent accidental logging.
"""

import os
import tomllib
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class CredentialError(Exception):
    """
    Raised when credentials cannot be loaded from any source.

    Indicates that environment variables, .env file, and config files all failed
    to provide required credentials.
    """


class SnowflakeCredentials(BaseSettings):
    """
    Snowflake connection credentials with environment variable fallback.

    Loads from:
    1. SNOWFLAKE_* environment variables
    2. .env file (automatic via pydantic-settings)
    3. Config file ([snowflake] section in .cubano.toml or ~/.config/cubano/config.toml)

    All password fields use SecretStr to mask values in logs and repr output.

    Attributes:
        account: Snowflake account identifier (e.g., 'xy12345.us-east-1')
        user: Username for authentication
        password: Password (masked in logs)
        warehouse: Warehouse name for query execution
        database: Database name
        role: Role to use (optional)
    """

    model_config = SettingsConfigDict(
        env_prefix="SNOWFLAKE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    account: str
    user: str
    password: SecretStr
    warehouse: str
    database: str
    role: str | None = None
    schema_: str | None = Field(default=None, alias="schema")

    @classmethod
    def load(cls, env_file: str | None = None, role: str | None = None) -> "SnowflakeCredentials":
        """
        Load credentials with fallback chain.

        Tries environment/env file first (automatic via pydantic-settings),
        then config files if that fails.

        The .env file path is resolved using this priority chain:
        1. ``CUBANO_ENV_FILE`` environment variable (highest priority)
        2. ``env_file`` parameter passed to this method
        3. Default ``".env"`` in the current working directory

        Args:
            env_file: Optional path to .env file. Overridden by CUBANO_ENV_FILE env var.
            role: Optional role override. When provided, replaces the role from env/config.
                Use when the caller knows which Snowflake role to activate (e.g., specific
                read-only role for tests). When None, role comes from SNOWFLAKE_ROLE env var
                or the [snowflake] config section (may itself be None).

        Returns:
            SnowflakeCredentials instance

        Raises:
            CredentialError: When no credentials found in any source

        Usage:
            try:
                creds = SnowflakeCredentials.load()
            except CredentialError as e:
                pytest.skip(f"Snowflake not available: {e}")
        """

        def _apply_role(creds: "SnowflakeCredentials") -> "SnowflakeCredentials":
            return creds.model_copy(update={"role": role}) if role is not None else creds

        # Determine which env_file to use (CUBANO_ENV_FILE > parameter > default)
        env_file_to_use = os.getenv("CUBANO_ENV_FILE") or env_file or ".env"

        # Try environment variables and .env file first (automatic via pydantic-settings)
        try:
            return _apply_role(cls(_env_file=env_file_to_use))  # type: ignore[call-arg]
        except Exception:
            pass

        # Try config files as fallback
        config_paths = [
            Path(".cubano.toml"),
            Path.home() / ".config" / "cubano" / "config.toml",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with config_path.open("rb") as f:
                        config = tomllib.load(f)
                    if "snowflake" in config:
                        return _apply_role(cls(**config["snowflake"]))
                except Exception:
                    continue

        # All sources failed
        raise CredentialError(
            "Snowflake credentials not found. Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
            "SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE environment "
            "variables or create .env file or .cubano.toml config file."
        )


class DatabricksCredentials(BaseSettings):
    """
    Databricks connection credentials with environment variable fallback.

    Loads from:
    1. DATABRICKS_* environment variables
    2. .env file (automatic via pydantic-settings)
    3. Config file ([databricks] section in .cubano.toml or ~/.config/cubano/config.toml)

    All token fields use SecretStr to mask values in logs and repr output.

    Attributes:
        server_hostname: Databricks workspace hostname
        http_path: SQL warehouse HTTP path
        access_token: Personal access token (masked in logs)
        catalog: Unity Catalog name (defaults to 'main')
    """

    model_config = SettingsConfigDict(
        env_prefix="DATABRICKS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    server_hostname: str
    http_path: str
    access_token: SecretStr
    catalog: str = "main"
    schema_: str | None = Field(default=None, alias="schema")

    @classmethod
    def load(cls, env_file: str | None = None) -> "DatabricksCredentials":
        """
        Load credentials with fallback chain.

        Tries environment/env file first (automatic via pydantic-settings),
        then config files if that fails.

        The .env file path is resolved using this priority chain:
        1. ``CUBANO_ENV_FILE`` environment variable (highest priority)
        2. ``env_file`` parameter passed to this method
        3. Default ``".env"`` in the current working directory

        Returns:
            DatabricksCredentials instance

        Raises:
            CredentialError: When no credentials found in any source

        Usage:
            try:
                creds = DatabricksCredentials.load()
            except CredentialError as e:
                pytest.skip(f"Databricks not available: {e}")
        """
        # Determine which env_file to use (CUBANO_ENV_FILE > parameter > default)
        env_file_to_use = os.getenv("CUBANO_ENV_FILE") or env_file or ".env"

        # Try environment variables and .env file first (automatic via pydantic-settings)
        try:
            return cls(_env_file=env_file_to_use)  # type: ignore[call-arg]
        except Exception:
            pass

        # Try config files as fallback
        config_paths = [
            Path(".cubano.toml"),
            Path.home() / ".config" / "cubano" / "config.toml",
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with config_path.open("rb") as f:
                        config = tomllib.load(f)
                    if "databricks" in config:
                        return cls(**config["databricks"])
                except Exception:
                    continue

        # All sources failed
        raise CredentialError(
            "Databricks credentials not found. Set DATABRICKS_SERVER_HOSTNAME, "
            "DATABRICKS_HTTP_PATH, DATABRICKS_ACCESS_TOKEN environment variables "
            "or create .env file or .cubano.toml config file."
        )
