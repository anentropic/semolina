"""
TOML configuration loading and pool factory.

Reads ``.semolina.toml`` connection sections and creates adbc-poolhouse
pools with the correct dialect, ready for ``register()``.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

from adbc_poolhouse import (
    DatabricksConfig,
    DuckDBConfig,
    SnowflakeConfig,
    create_pool,
)

from .dialect import Dialect

_CONFIG_MAP: dict[str, tuple[type, Dialect]] = {
    "snowflake": (SnowflakeConfig, Dialect.SNOWFLAKE),
    "databricks": (DatabricksConfig, Dialect.DATABRICKS),
    "duckdb": (DuckDBConfig, Dialect.DUCKDB),
}


def _load_semantic_views(dbapi_conn: Any, connection_record: Any) -> None:
    """
    Auto-install and load the semantic_views extension on new DuckDB connections.

    Registered as a SQLAlchemy pool ``connect`` event listener. Fires once per
    physical ADBC connection creation. ``INSTALL`` is idempotent (no-op when
    cached at ``~/.duckdb/extensions/``). ``LOAD`` activates the extension in
    the current connection session.
    """
    cur = dbapi_conn.cursor()
    cur.execute("INSTALL semantic_views FROM community")
    cur.execute("LOAD semantic_views")
    cur.close()


def _expand_private_key_path(config: Any) -> Any:
    """
    Expand ``~`` in a Snowflake config's ``private_key_path``.

    The native snowflake-connector expands ``~`` itself, but the Go-based
    Snowflake ADBC driver opens the path literally and fails with "could not read
    private key file" on a ``~/...`` path. Expanding here makes both work. Configs
    without a ``private_key_path`` field (Databricks, DuckDB) pass through.
    """
    key_path = getattr(config, "private_key_path", None)
    if key_path is not None:
        return config.model_copy(update={"private_key_path": Path(key_path).expanduser()})
    return config


def pool_from_config(
    connection: str = "default",
    config_path: str | Path = ".semolina.toml",
) -> tuple[Any, Dialect]:
    """
    Create a (pool, Dialect) tuple from .semolina.toml config.

    Reads the named connection section, determines the warehouse type
    from the ``type`` field, instantiates the appropriate adbc-poolhouse
    config class with the remaining fields, and creates a connection pool.

    Args:
        connection: Name of the connection section in ``[connections.X]``.
        config_path: Path to the TOML config file.

    Returns:
        Tuple of ``(pool, Dialect)`` ready for ``register()``.
        The pool is a ``sqlalchemy.pool.QueuePool`` (typed as ``Any``
        to avoid requiring sqlalchemy as a direct import).

    Raises:
        FileNotFoundError: If config file does not exist.
        KeyError: If the named connection section is not found.
        ValueError: If the ``type`` field is missing or unsupported.

    Example:
        .. code-block:: python

            from semolina.config import pool_from_config

            pool, dialect = pool_from_config(connection="default")
    """
    path = Path(config_path)
    with path.open("rb") as f:
        config = tomllib.load(f)

    connections: dict[str, Any] = config.get("connections", {})
    if connection not in connections:
        available = list(connections.keys())
        raise KeyError(
            f"Connection '{connection}' not found in {config_path}. "
            f"Available connections: {available}"
        )

    section = dict(connections[connection])
    conn_type = section.pop("type", None)
    if conn_type is None:
        raise ValueError(
            f"Connection '{connection}' in {config_path} is missing "
            "required 'type' field (e.g. type = \"snowflake\")"
        )

    if conn_type not in _CONFIG_MAP:
        supported = list(_CONFIG_MAP.keys())
        raise ValueError(f"Unsupported connection type '{conn_type}'. Supported types: {supported}")

    config_cls, dialect = _CONFIG_MAP[conn_type]
    wh_config = _expand_private_key_path(config_cls(**section))
    pool = create_pool(wh_config)

    if conn_type == "duckdb":
        from sqlalchemy import event

        event.listen(pool, "connect", _load_semantic_views)

    return pool, dialect


def warehouse_config(
    backend: str,
    config_path: str | Path = ".semolina.toml",
) -> Any:
    """
    Build an adbc-poolhouse config for a backend without creating a pool.

    Reads the ``[connections.<backend>]`` section of ``.semolina.toml`` (if the
    file exists) and instantiates the matching adbc-poolhouse config class.
    ``SNOWFLAKE_*`` / ``DATABRICKS_*`` / ``DUCKDB_*`` environment variables (and a
    ``.env`` file, overridable with ``SEMOLINA_ENV_FILE``) fill any fields not
    given in the section, so env-only setups work with no TOML file. Both password
    and key-pair auth are supported (whatever the config class accepts).

    Unlike :func:`pool_from_config`, the section is looked up by backend *type*
    (``"snowflake"`` / ``"databricks"`` / ``"duckdb"``), matching how the codegen
    CLI and the integration test fixtures select a backend.

    Args:
        backend: ``"snowflake"``, ``"databricks"``, or ``"duckdb"``.
        config_path: Path to the TOML config file.

    Returns:
        An adbc-poolhouse config instance (``SnowflakeConfig`` etc.).

    Raises:
        ValueError: If ``backend`` is not a supported type.
        pydantic.ValidationError: If required fields are missing from both the
            config section and the environment.
    """
    if backend not in _CONFIG_MAP:
        supported = list(_CONFIG_MAP.keys())
        raise ValueError(f"Unsupported backend '{backend}'. Supported types: {supported}")

    config_cls, _dialect = _CONFIG_MAP[backend]
    section: dict[str, Any] = {}
    path = Path(config_path)
    if path.exists():
        with path.open("rb") as f:
            data = tomllib.load(f)
        section = dict(data.get("connections", {}).get(backend, {}))
        section.pop("type", None)
    # Precedence: TOML section > environment > .env file (SEMOLINA_ENV_FILE
    # overrides the default ".env"). A missing .env file is ignored.
    env_file = os.getenv("SEMOLINA_ENV_FILE") or ".env"
    return _expand_private_key_path(config_cls(**section, _env_file=env_file))


def snowflake_connect_kwargs(config: Any) -> dict[str, Any]:
    """
    Map a poolhouse ``SnowflakeConfig`` to ``snowflake.connector.connect`` kwargs.

    Drives the native Snowflake connector (used by the codegen ``SnowflakeEngine``
    and the integration test DDL setup). Emits ``password`` for password auth, or
    ``private_key_file`` / ``private_key_file_pwd`` for key-pair auth.

    Args:
        config: A poolhouse ``SnowflakeConfig`` instance.

    Returns:
        Keyword arguments for ``snowflake.connector.connect()``.
    """
    kwargs: dict[str, Any] = {"account": config.account}
    if config.user:
        kwargs["user"] = config.user
    if config.warehouse:
        kwargs["warehouse"] = config.warehouse
    if config.database:
        kwargs["database"] = config.database
    if config.role:
        kwargs["role"] = config.role
    if config.schema_:
        kwargs["schema"] = config.schema_
    if config.password is not None:
        kwargs["password"] = config.password.get_secret_value()
    if config.private_key_path is not None:
        kwargs["private_key_file"] = str(config.private_key_path)
        # Only pass a passphrase for an *encrypted* key. An empty/placeholder
        # passphrase makes snowflake.connector reject an unencrypted key with
        # "Password was given but private key is not encrypted."
        passphrase = (
            config.private_key_passphrase.get_secret_value()
            if config.private_key_passphrase is not None
            else None
        )
        if passphrase:
            kwargs["private_key_file_pwd"] = passphrase.encode()
    return kwargs


def databricks_connect_kwargs(config: Any) -> dict[str, Any]:
    """
    Map a poolhouse ``DatabricksConfig`` to ``databricks.sql.connect`` kwargs.

    Drives the native Databricks connector (used by the codegen
    ``DatabricksEngine`` and the integration test DDL setup).

    Args:
        config: A poolhouse ``DatabricksConfig`` instance.

    Returns:
        Keyword arguments for ``databricks.sql.connect()``.
    """
    kwargs: dict[str, Any] = {}
    if config.host:
        kwargs["server_hostname"] = config.host
    if config.http_path:
        kwargs["http_path"] = config.http_path
    if config.token is not None:
        kwargs["access_token"] = config.token.get_secret_value()
    if config.catalog:
        kwargs["catalog"] = config.catalog
    if config.schema_:
        kwargs["schema"] = config.schema_
    return kwargs
