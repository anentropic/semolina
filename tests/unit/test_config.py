"""Tests for the TOML configuration loading and pool factory module."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event

from semolina.config import _load_semantic_views, pool_from_config
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

        pool_from_config(connection="default", config_path=toml_file)

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

        pool_from_config(connection="default", config_path=toml_file)

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

        pool_from_config(connection="default", config_path=toml_file)

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

        pool_from_config(connection="default", config_path=toml_file)

        # 'type' should not appear in the kwargs passed to the config class
        call_kwargs = mock_config_map["snowflake_cls"].call_args[1]
        assert "type" not in call_kwargs


# ---------------------------------------------------------------------------
# TestPoolFromConfig
# ---------------------------------------------------------------------------


class TestPoolFromConfig:
    """Tests for pool_from_config() factory function."""

    @patch("semolina.config.create_pool")
    def test_returns_pool_dialect_tuple(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """pool_from_config() returns a 2-tuple of (pool, Dialect)."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        fake_pool = MagicMock()
        mock_create_pool.return_value = fake_pool

        result = pool_from_config(connection="default", config_path=toml_file)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] is fake_pool

    @patch("semolina.config.create_pool")
    def test_default_connection_name(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """pool_from_config() with no args uses connection='default'."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        mock_create_pool.return_value = MagicMock()

        # Should not raise -- reads [connections.default]
        pool_from_config(config_path=toml_file)

        mock_config_map["snowflake_cls"].assert_called_once()

    @patch("semolina.config.create_pool")
    def test_named_connection(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """pool_from_config(connection='analytics') reads that section."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.analytics]\ntype = "databricks"\nhost = "adb-xxx.net"\n',
        )
        mock_create_pool.return_value = MagicMock()

        pool_from_config(connection="analytics", config_path=toml_file)

        mock_config_map["databricks_cls"].assert_called_once_with(host="adb-xxx.net")

    @patch("semolina.config.create_pool")
    def test_snowflake_returns_snowflake_dialect(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """type='snowflake' returns Dialect.SNOWFLAKE in tuple."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        mock_create_pool.return_value = MagicMock()

        _, dialect = pool_from_config(connection="default", config_path=toml_file)

        assert dialect is Dialect.SNOWFLAKE

    @patch("semolina.config.create_pool")
    def test_databricks_returns_databricks_dialect(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """type='databricks' returns Dialect.DATABRICKS in tuple."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "databricks"\nhost = "adb-xxx.net"\n',
        )
        mock_create_pool.return_value = MagicMock()

        _, dialect = pool_from_config(connection="default", config_path=toml_file)

        assert dialect is Dialect.DATABRICKS

    @patch("semolina.config.create_pool")
    def test_duckdb_returns_duckdb_dialect(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """type='duckdb' returns Dialect.DUCKDB in tuple."""
        from sqlalchemy.pool import QueuePool

        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "duckdb"\ndatabase = "/tmp/test.db"\n',
        )
        mock_create_pool.return_value = QueuePool(lambda: MagicMock(), pool_size=1)

        _, dialect = pool_from_config(connection="default", config_path=toml_file)

        assert dialect is Dialect.DUCKDB

    @patch("semolina.config.create_pool")
    def test_toml_fields_passed_as_kwargs(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """Config class receives TOML fields as keyword args (minus type)."""
        toml_file = _write_toml(
            tmp_path,
            (
                "[connections.default]\n"
                'type = "snowflake"\n'
                'account = "xy12345"\n'
                'user = "myuser"\n'
                'database = "analytics"\n'
                'warehouse = "compute_wh"\n'
            ),
        )
        mock_create_pool.return_value = MagicMock()

        pool_from_config(connection="default", config_path=toml_file)

        mock_config_map["snowflake_cls"].assert_called_once_with(
            account="xy12345",
            user="myuser",
            database="analytics",
            warehouse="compute_wh",
        )


# ---------------------------------------------------------------------------
# TestConfigErrors
# ---------------------------------------------------------------------------


class TestConfigErrors:
    """Tests for error handling in pool_from_config()."""

    def test_missing_file_raises_file_not_found(self):
        """FileNotFoundError for nonexistent path."""
        with pytest.raises(FileNotFoundError):
            pool_from_config(config_path="/nonexistent/path/.semolina.toml")

    def test_missing_connection_raises_key_error(self, tmp_path: Path):
        """KeyError when connection name not in TOML."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        with pytest.raises(KeyError):
            pool_from_config(connection="nonexistent", config_path=toml_file)

    def test_missing_connection_shows_available(self, tmp_path: Path):
        """KeyError message includes available connection names."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        with pytest.raises(KeyError, match="default"):
            pool_from_config(connection="nonexistent", config_path=toml_file)

    def test_missing_type_raises_value_error(self, tmp_path: Path):
        """ValueError when type field absent."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="type"):
            pool_from_config(connection="default", config_path=toml_file)

    def test_unsupported_type_raises_value_error(self, tmp_path: Path):
        """ValueError for type='unknown'."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "unknown"\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="unknown"):
            pool_from_config(connection="default", config_path=toml_file)

    def test_unsupported_type_shows_supported(self, tmp_path: Path):
        """ValueError message includes supported types list."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "unknown"\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="snowflake"):
            pool_from_config(connection="default", config_path=toml_file)

    def test_unsupported_type_shows_duckdb_in_supported(self, tmp_path: Path):
        """ValueError for unknown type includes 'duckdb' in supported list."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "unknown"\naccount = "xy12345"\n',
        )
        with pytest.raises(ValueError, match="duckdb"):
            pool_from_config(connection="default", config_path=toml_file)


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

    @patch("semolina.config.create_pool")
    def test_duckdb_pool_has_semantic_views_listener(
        self,
        mock_create_pool: MagicMock,
        tmp_path: Path,
    ):
        """pool_from_config() for DuckDB attaches _load_semantic_views listener."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "duckdb"\ndatabase = ":memory:"\n',
        )
        from sqlalchemy.pool import QueuePool

        real_pool = QueuePool(lambda: MagicMock(), pool_size=1)
        mock_create_pool.return_value = real_pool

        pool, _dialect = pool_from_config(connection="default", config_path=toml_file)

        assert event.contains(pool, "connect", _load_semantic_views)

    @patch("semolina.config.create_pool")
    def test_snowflake_pool_no_semantic_views_listener(
        self,
        mock_create_pool: MagicMock,
        mock_config_map: dict[str, MagicMock],
        tmp_path: Path,
    ):
        """pool_from_config() for Snowflake does NOT attach _load_semantic_views."""
        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "snowflake"\naccount = "xy12345"\n',
        )
        from sqlalchemy.pool import QueuePool

        real_pool = QueuePool(lambda: MagicMock(), pool_size=1)
        mock_create_pool.return_value = real_pool

        pool, _dialect = pool_from_config(connection="default", config_path=toml_file)

        assert not event.contains(pool, "connect", _load_semantic_views)

    def test_duckdb_pool_extension_loaded(self, tmp_path: Path):
        """DuckDB pool created by pool_from_config() auto-loads the extension."""
        pytest.importorskip("adbc_driver_duckdb")

        toml_file = _write_toml(
            tmp_path,
            '[connections.default]\ntype = "duckdb"\ndatabase = ":memory:"\n',
        )
        pool, _dialect = pool_from_config(connection="default", config_path=toml_file)

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
