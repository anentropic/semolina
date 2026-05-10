"""
TOML configuration loading and pool factory.

Reads ``.semolina.toml`` connection sections and creates adbc-poolhouse
pools with the correct dialect, ready for ``register()``.
"""

from __future__ import annotations

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
    warehouse_config = config_cls(**section)
    pool = create_pool(warehouse_config)

    if conn_type == "duckdb":
        from sqlalchemy import event

        event.listen(pool, "connect", _load_semantic_views)

    return pool, dialect
