"""Tests for the TOML configuration loading and engine factory module."""
# RED-first (Phase 44 Wave 0): create_engine lands in Plan 02. Until then
# basedpyright strict cannot see it, so scope-disable the rules the not-yet-built
# API triggers in the TestCreateEngine class. Plan 02 REMOVES this pragma when the
# tests go GREEN (it is intentionally not a `# type: ignore`).
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event

from semolina.config import _load_semantic_views, create_engine
from semolina.dialect import Dialect

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_toml(tmp_path: Path, content: str) -> Path:
    """Write TOML content to a temp file and return the path."""
    toml_file = tmp_path / ".semolina.toml"
    toml_file.write_text(content)
    return toml_file


@pytest.fixture()
def mock_config_map():
    """Patch _CONFIG_MAP with mock config classes for isolated testing."""
    mock_sf = MagicMock()
    mock_db = MagicMock()
    mock_dk = MagicMock()
    patched_map: dict[str, tuple[type, Dialect]] = {
        "snowflake": (mock_sf, Dialect.SNOWFLAKE),
        "databricks": (mock_db, Dialect.DATABRICKS),
        "duckdb": (mock_dk, Dialect.DUCKDB),
    }
    with patch("semolina.config._CONFIG_MAP", patched_map):
        yield {"snowflake_cls": mock_sf, "databricks_cls": mock_db, "duckdb_cls": mock_dk}


# ---------------------------------------------------------------------------
# TestConfigDispatch
# ---------------------------------------------------------------------------


class TestConfigDispatch:
    """Tests for the _CONFIG_MAP type dispatch."""

    @patch("semolina.config.create_pool")
    def test_snowflake_type_creates_snowflake_config(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """TOML with type='snowflake' dispatches to SnowflakeConfig."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        mock_create_pool.return_value = MagicMock()

        create_engine("default", config_path=toml_file)

        mock_config_map["snowflake_cls"].assert_called_once_with(account="xy12345")

    @patch("semolina.config.create_pool")
    def test_databricks_type_creates_databricks_config(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """TOML with type='databricks' dispatches to DatabricksConfig."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "databricks"\nhost = "adb-xxx.net"\n',
        )
        mock_create_pool.return_value = MagicMock()

        create_engine("default", config_path=toml_file)

        mock_config_map["databricks_cls"].assert_called_once_with(host="adb-xxx.net")

    @patch("semolina.config.create_pool")
    def test_duckdb_type_creates_duckdb_config(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """TOML with type='duckdb' dispatches to DuckDBConfig."""
        from sqlalchemy.pool import QueuePool

        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "duckdb"\ndatabase = "/tmp/test.db"\n',
        )
        mock_create_pool.return_value = QueuePool(lambda: MagicMock(), pool_size=1)

        create_engine("default", config_path=toml_file)

        mock_config_map["duckdb_cls"].assert_called_once_with(database="/tmp/test.db")

    @patch("semolina.config.create_pool")
    def test_type_field_popped_before_config_class(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """The 'type' key is NOT passed to config class constructor."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        mock_create_pool.return_value = MagicMock()

        create_engine("default", config_path=toml_file)

        # 'type' should not appear in the kwargs passed to the config class
        call_kwargs = mock_config_map["snowflake_cls"].call_args[1]
        assert "type" not in call_kwargs


# ---------------------------------------------------------------------------
# TestConfigErrors
# ---------------------------------------------------------------------------


class TestConfigErrors:
    """Tests for error handling in create_engine() name dispatch."""

    def test_missing_file_raises_file_not_found(self):
        """FileNotFoundError for nonexistent path."""
        with pytest.raises(FileNotFoundError):
            create_engine("default", config_path="/nonexistent/path/.semolina.toml")

    def test_missing_connection_raises_key_error(self, tmp_path: Path):
        """KeyError when connection name not in TOML."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        with pytest.raises(KeyError):
            create_engine("nonexistent", config_path=toml_file)

    def test_missing_connection_shows_available(self, tmp_path: Path):
        """KeyError message includes available connection names."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        with pytest.raises(KeyError, match="default"):
            create_engine("nonexistent", config_path=toml_file)

    def test_missing_type_raises_value_error(self, tmp_path: Path):
        """ValueError when type field absent."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="type"):
            create_engine("default", config_path=toml_file)

    def test_unsupported_type_raises_value_error(self, tmp_path: Path):
        """ValueError for type='unknown'."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "unknown"\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="unknown"):
            create_engine("default", config_path=toml_file)

    def test_unsupported_type_shows_supported(self, tmp_path: Path):
        """ValueError message includes supported types list."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "unknown"\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="snowflake"):
            create_engine("default", config_path=toml_file)

    def test_unsupported_type_shows_duckdb_in_supported(self, tmp_path: Path):
        """ValueError for unknown type includes 'duckdb' in supported list."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "unknown"\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="duckdb"):
            create_engine("default", config_path=toml_file)


# ---------------------------------------------------------------------------
# TestSemanticViewsListener
# ---------------------------------------------------------------------------


class TestSemanticViewsListener:
    """Tests for _load_semantic_views event listener and DuckDB auto-wiring."""

    def test_load_semantic_views_is_callable(self):
        """_load_semantic_views function exists and is callable."""
        assert callable(_load_semantic_views)

    def test_load_semantic_views_signature(self):
        """_load_semantic_views accepts (dbapi_conn, connection_record) params."""
        sig = inspect.signature(_load_semantic_views)
        params = list(sig.parameters.keys())
        assert len(params) == 2
        assert params[0] == "dbapi_conn"
        assert params[1] == "connection_record"

    def test_duckdb_pool_extension_loaded(self, tmp_path: Path):
        """DuckDB engine created by create_engine() auto-loads the extension."""
        pytest.importorskip("adbc_driver_duckdb")

        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "duckdb"\ndatabase = ":memory:"\n',
        )
        engine = create_engine("default", config_path=toml_file)
        pool = engine._pool

        try:
            with pool.connect() as conn:
                cur = conn.cursor()
                # Verify the semantic_views extension is loaded by checking
                # duckdb_extensions() for installed=true and loaded=true.
                cur.execute(
                    "SELECT installed, loaded FROM duckdb_extensions()"
                    " WHERE extension_name = 'semantic_views'"
                )
                row = cur.fetchone()
                assert row is not None, "semantic_views extension not found"
                installed, loaded = row
                assert installed, "semantic_views extension not installed"
                assert loaded, "semantic_views extension not loaded"
                cur.close()
        finally:
            from adbc_poolhouse import close_pool

            close_pool(pool)


# ---------------------------------------------------------------------------
# TestAsyncPoolContract
# ---------------------------------------------------------------------------


class TestAsyncPoolContract:
    """Tests for the guard over adbc-poolhouse's undocumented inner sync pool."""

    def test_create_async_engine_reports_a_missing_inner_pool(self):
        """
        A poolhouse release without ``AsyncPool._pool`` raises a message naming the cause.

        ``AsyncPool`` publishes only ``connect()`` and ``close()``, so the
        listener attach reaches into an attribute that carries no compatibility
        promise — and the ``adbc-poolhouse`` pin has no upper bound. Without a
        guard, a rename surfaces as a bare ``AttributeError`` from inside
        ``create_async_engine`` that names neither the package that changed nor
        anything the reader can do about it.
        """
        pytest.importorskip("adbc_driver_duckdb")
        from adbc_poolhouse import DuckDBConfig

        from semolina.config import create_async_engine

        # Only connect() and close(): the 1.6.2 public AsyncPool surface, minus
        # the private attribute Semolina currently depends on.
        bare_pool = SimpleNamespace(connect=lambda: None, close=lambda: None)

        with (
            patch("adbc_poolhouse.create_async_pool", return_value=bare_pool),
            pytest.raises(RuntimeError, match="adbc-poolhouse"),
        ):
            create_async_engine(DuckDBConfig(database=":memory:", pool_size=1))


# ---------------------------------------------------------------------------
# TestCreateEngine (Phase 44 D1: create_engine config-object | TOML-name dispatch)
# ---------------------------------------------------------------------------


class TestCreateEngine:
    """
    Tests for the create_engine() factory (Phase 44 D1).

    create_engine accepts either an adbc-poolhouse config object
    (``SnowflakeConfig(...)`` / ``DuckDBConfig(...)``) or a ``.semolina.toml``
    connection name. It builds an Engine that owns one ADBC pool plus the dialect
    derived from the config type via the reverse ``_CONFIG_MAP`` lookup. These
    tests patch ``semolina.config.create_pool`` to avoid a live connect.

    RED until Plan 02 lands ``create_engine``; the import below fails loudly.
    """

    @patch("semolina.config.create_pool")
    def test_create_engine_config_object_snowflake_dialect(
        self,
        mock_create_pool: MagicMock,
    ):
        """create_engine(SnowflakeConfig(...)) returns an Engine with the Snowflake dialect."""
        from adbc_poolhouse import SnowflakeConfig
        from pydantic import SecretStr

        from semolina.config import create_engine
        from semolina.engines.sql import SnowflakeDialect

        mock_create_pool.return_value = MagicMock()

        engine = create_engine(
            SnowflakeConfig(account="xy12345", user="u", password=SecretStr("p"))
        )

        assert isinstance(engine.dialect, SnowflakeDialect)
        # The Engine owns the pool create_pool produced.
        assert engine._pool is mock_create_pool.return_value

    @patch("semolina.config.create_pool")
    def test_create_engine_config_object_duckdb_dialect(
        self,
        mock_create_pool: MagicMock,
    ):
        """create_engine(DuckDBConfig(...)) returns an Engine with the DuckDB dialect."""
        from adbc_poolhouse import DuckDBConfig
        from sqlalchemy.pool import QueuePool

        from semolina.config import create_engine
        from semolina.engines.sql import DuckDBDialect

        mock_create_pool.return_value = QueuePool(lambda: MagicMock(), pool_size=1)

        engine = create_engine(DuckDBConfig(database=":memory:"))

        assert isinstance(engine.dialect, DuckDBDialect)

    @patch("semolina.config.create_pool")
    def test_create_engine_duckdb_attaches_semantic_views_listener(
        self,
        mock_create_pool: MagicMock,
    ):
        """create_engine(DuckDBConfig(...)) attaches the _load_semantic_views connect listener."""
        from adbc_poolhouse import DuckDBConfig
        from sqlalchemy.pool import QueuePool

        from semolina.config import create_engine

        real_pool = QueuePool(lambda: MagicMock(), pool_size=1)
        mock_create_pool.return_value = real_pool

        engine = create_engine(DuckDBConfig(database=":memory:"))

        assert event.contains(engine._pool, "connect", _load_semantic_views)

    @patch("semolina.config.create_pool")
    def test_create_engine_snowflake_no_semantic_views_listener(
        self,
        mock_create_pool: MagicMock,
    ):
        """create_engine(SnowflakeConfig(...)) does NOT attach the DuckDB connect listener."""
        from adbc_poolhouse import SnowflakeConfig
        from pydantic import SecretStr
        from sqlalchemy.pool import QueuePool

        from semolina.config import create_engine

        real_pool = QueuePool(lambda: MagicMock(), pool_size=1)
        mock_create_pool.return_value = real_pool

        engine = create_engine(
            SnowflakeConfig(account="xy12345", user="u", password=SecretStr("p"))
        )

        assert not event.contains(engine._pool, "connect", _load_semantic_views)

    @patch("semolina.config.create_pool")
    def test_create_engine_name_dispatch_reads_toml(
        self,
        mock_create_pool: MagicMock,
        tmp_path: Path,
    ):
        """create_engine("default", config_path=...) reads [connections.default] from TOML."""
        from semolina.config import create_engine
        from semolina.engines.sql import SnowflakeDialect

        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\nuser = "u"\n'
            'password = "p"\n',
        )
        mock_create_pool.return_value = MagicMock()

        engine = create_engine("default", config_path=toml_file)

        assert isinstance(engine.dialect, SnowflakeDialect)

    @patch("semolina.config.create_pool")
    def test_create_engine_name_dispatch_named_connection(
        self,
        mock_create_pool: MagicMock,
        tmp_path: Path,
    ):
        """create_engine("analytics", config_path=...) reads that named section."""
        from sqlalchemy.pool import QueuePool

        from semolina.config import create_engine
        from semolina.engines.sql import DuckDBDialect

        toml_file = _write_toml(
            tmp_path,
            '[connections.analytics]\ntype = "duckdb"\ndatabase = ":memory:"\n',
        )
        # DuckDB attaches a connect listener, so create_pool must return a real pool.
        mock_create_pool.return_value = QueuePool(lambda: MagicMock(), pool_size=1)

        engine = create_engine("analytics", config_path=toml_file)

        assert isinstance(engine.dialect, DuckDBDialect)


# ---------------------------------------------------------------------------
# TestDialectForConfigType
# ---------------------------------------------------------------------------


class TestDialectForConfigType:
    """
    Tests for the _dialect_for_config_type reverse lookup (Phase 44 IN-03).

    The lookup must resolve each config class to its dialect by *exact* type, so
    the result is independent of ``_CONFIG_MAP`` insertion order and cannot be
    skewed by a future config subclass relationship.
    """

    def test_snowflake_config_maps_to_snowflake_dialect(self):
        """A SnowflakeConfig resolves to Dialect.SNOWFLAKE."""
        from adbc_poolhouse import SnowflakeConfig
        from pydantic import SecretStr

        from semolina.config import _dialect_for_config_type

        config = SnowflakeConfig(account="xy12345", user="u", password=SecretStr("p"))
        assert _dialect_for_config_type(config) is Dialect.SNOWFLAKE

    def test_databricks_config_maps_to_databricks_dialect(self):
        """A DatabricksConfig resolves to Dialect.DATABRICKS."""
        from adbc_poolhouse import DatabricksConfig
        from pydantic import SecretStr

        from semolina.config import _dialect_for_config_type

        config = DatabricksConfig(
            host="workspace.cloud.databricks.com",
            http_path="/sql/1.0/warehouses/abc123",
            token=SecretStr("dapi..."),
        )
        assert _dialect_for_config_type(config) is Dialect.DATABRICKS

    def test_duckdb_config_maps_to_duckdb_dialect(self):
        """A DuckDBConfig resolves to Dialect.DUCKDB."""
        from adbc_poolhouse import DuckDBConfig

        from semolina.config import _dialect_for_config_type

        config = DuckDBConfig(database=":memory:")
        assert _dialect_for_config_type(config) is Dialect.DUCKDB

    def test_subclass_does_not_resolve_by_isinstance(self):
        """
        A subclass of a known config is NOT silently matched to the parent's dialect.

        Exact-type matching means an unregistered subclass raises rather than
        inheriting the parent's dialect by an order-dependent isinstance scan.
        """
        from adbc_poolhouse import DuckDBConfig

        from semolina.config import _dialect_for_config_type

        class CustomDuckDBConfig(DuckDBConfig):
            pass

        config = CustomDuckDBConfig(database=":memory:")
        with pytest.raises(ValueError, match="Unsupported config type 'CustomDuckDBConfig'"):
            _dialect_for_config_type(config)

    def test_unknown_config_type_raises_value_error(self):
        """An entirely unrelated object raises a clear ValueError listing supported configs."""
        from semolina.config import _dialect_for_config_type

        with pytest.raises(ValueError, match="Unsupported config type 'object'"):
            _dialect_for_config_type(object())
