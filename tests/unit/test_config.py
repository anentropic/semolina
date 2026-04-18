"""Tests for the TOML configuration loading and pool factory module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from semolina.config import pool_from_config
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
    patched_map: dict[str, tuple[type, Dialect]] = {
        "snowflake": (mock_sf, Dialect.SNOWFLAKE),
        "databricks": (mock_db, Dialect.DATABRICKS),
    }
    with patch("semolina.config._CONFIG_MAP", patched_map):
        yield {"snowflake_cls": mock_sf, "databricks_cls": mock_db}


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
