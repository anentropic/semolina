"""
TOML configuration loading and the ``create_engine`` factory.

Reads ``.semolina.toml`` connection sections (or accepts an adbc-poolhouse
config object directly) and builds an :class:`~semolina.engines.base.Engine`
that owns one ADBC pool plus the dialect derived from the config type.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from adbc_poolhouse import (
    DatabricksConfig,
    DuckDBConfig,
    SnowflakeConfig,
    create_pool,
)

from .dialect import Dialect, resolve_dialect

if TYPE_CHECKING:
    from .engines.base import Engine

# adbc-poolhouse config objects accepted by create_engine.
WarehouseConfig = SnowflakeConfig | DatabricksConfig | DuckDBConfig

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


def _dialect_for_config_type(config: Any) -> Dialect:
    """
    Reverse-look up the :class:`Dialect` for an adbc-poolhouse config object.

    Built off the same ``_CONFIG_MAP`` that the TOML path uses, keyed by the
    config *class* rather than the ``type`` string, so a config object and its
    equivalent ``[connections.<name>]`` section resolve to the same dialect.

    Args:
        config: An adbc-poolhouse config instance (``SnowflakeConfig`` etc.).

    Returns:
        The :class:`Dialect` enum value for the config's backend.

    Raises:
        ValueError: If the config type is not a supported backend.
    """
    for config_cls, dialect in _CONFIG_MAP.values():
        if isinstance(config, config_cls):
            return dialect
    supported = [cls.__name__ for cls, _ in _CONFIG_MAP.values()]
    raise ValueError(
        f"Unsupported config type '{type(config).__name__}'. Supported configs: {supported}"
    )


def _engine_cls_for_dialect(dialect: Dialect) -> type[Engine]:
    """
    Select the backend ``Engine`` subclass for a dialect.

    Keeps subclass selection in one place (mirroring ``_CONFIG_MAP`` keying) so
    callers never pick an Engine subclass by hand.

    Args:
        dialect: The :class:`Dialect` derived from the config type.

    Returns:
        The concrete ``Engine`` subclass for the backend.
    """
    from .engines.databricks import DatabricksEngine
    from .engines.duckdb import DuckDBEngine
    from .engines.snowflake import SnowflakeEngine

    engine_map: dict[Dialect, type[Engine]] = {
        Dialect.SNOWFLAKE: SnowflakeEngine,
        Dialect.DATABRICKS: DatabricksEngine,
        Dialect.DUCKDB: DuckDBEngine,
    }
    return engine_map[dialect]


def create_engine(
    config: WarehouseConfig | str = "default",
    *,
    config_path: str | Path = ".semolina.toml",
) -> Engine:
    """
    Build an :class:`~semolina.engines.base.Engine` from a config object or name.

    The single public construction entry point (the SQLAlchemy
    ``create_engine`` parallel). Accepts **either** an adbc-poolhouse config
    object (``SnowflakeConfig(...)`` / ``DatabricksConfig(...)`` /
    ``DuckDBConfig(...)``) **or** a ``.semolina.toml`` connection name. It
    creates one ADBC pool, derives the dialect from the config type, wires the
    DuckDB ``semantic_views`` connect listener when applicable, and returns the
    matching backend Engine subclass owning that pool and dialect.

    Args:
        config: An adbc-poolhouse config object, or the name of a
            ``[connections.<name>]`` section in ``.semolina.toml`` (defaults to
            ``"default"``). There is no URL-string form.
        config_path: Path to the TOML config file. Only consulted when ``config``
            is a connection-name string.

    Returns:
        An :class:`~semolina.engines.base.Engine` owning one ADBC pool plus the
        dialect derived from the config type.

    Raises:
        FileNotFoundError: If a connection name is given but the config file
            does not exist.
        KeyError: If the named connection section is not found.
        ValueError: If the connection ``type`` (or config object type) is
            missing or unsupported.

    Example:
        .. code-block:: python

            from adbc_poolhouse import SnowflakeConfig

            from semolina.config import create_engine

            engine = create_engine(SnowflakeConfig(account="xy12345", user="u"))
            # or, reading [connections.default] from .semolina.toml:
            engine = create_engine("default")
    """
    if isinstance(config, str):
        wh_config, dialect = _read_connection(config, config_path)
    else:
        wh_config = _expand_private_key_path(config)
        dialect = _dialect_for_config_type(config)

    pool = create_pool(wh_config)

    if dialect is Dialect.DUCKDB:
        from sqlalchemy import event

        event.listen(pool, "connect", _load_semantic_views)

    dialect_instance = resolve_dialect(dialect)
    engine_cls = _engine_cls_for_dialect(dialect)
    return engine_cls(pool=pool, dialect=dialect_instance, config=wh_config)


def _read_connection(
    connection: str,
    config_path: str | Path,
) -> tuple[Any, Dialect]:
    """
    Read a ``[connections.<name>]`` section into a (config, Dialect) pair.

    The TOML-reading half of :func:`create_engine`'s name-dispatch arm (folded
    out of the former public ``pool_from_config``): reads the section, pops
    ``type``, instantiates the matching config class, and expands any private
    key path. The pool is created by the caller.

    Args:
        connection: Name of the ``[connections.<name>]`` section.
        config_path: Path to the TOML config file.

    Returns:
        Tuple of ``(config_instance, Dialect)``.

    Raises:
        FileNotFoundError: If the config file does not exist.
        KeyError: If the named connection section is not found.
        ValueError: If the ``type`` field is missing or unsupported.
    """
    path = Path(config_path)
    with path.open("rb") as f:
        data = tomllib.load(f)

    connections: dict[str, Any] = data.get("connections", {})
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
    return wh_config, dialect


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
