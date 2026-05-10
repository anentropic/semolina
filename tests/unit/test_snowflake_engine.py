"""
Comprehensive unit tests for SnowflakeEngine using unittest.mock.

Tests cover:
- Lazy import and initialization
- SQL generation delegation to SQLBuilder
- Connection lifecycle with context managers
- Result mapping from tuples to dicts
- Error handling and translation
- End-to-end integration flows
- Introspection of Snowflake semantic views via SHOW COLUMNS

All tests use unittest.mock to simulate Snowflake connector behavior without
requiring actual Snowflake warehouse access.
"""

import json
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from models import Sales

from semolina.query import _Query


class _SnowflakeProgrammingError(Exception):
    """Minimal stub for snowflake.connector.errors.ProgrammingError."""

    def __init__(self, msg: str = "", errno: int = 0, sqlstate: str = "") -> None:
        self.msg = msg
        self.errno = errno
        self.sqlstate = sqlstate
        super().__init__(msg)


class _SnowflakeDatabaseError(Exception):
    """Minimal stub for snowflake.connector.errors.DatabaseError."""

    def __init__(self, msg: str = "", errno: int = 0, sqlstate: str = "") -> None:
        self.msg = msg
        self.errno = errno
        self.sqlstate = sqlstate
        super().__init__(msg)


@pytest.fixture(autouse=True)
def _mock_snowflake_in_sys_modules():  # pyright: ignore[reportUnusedFunction]
    """
    Pre-populate sys.modules with snowflake mocks for the duration of every test.

    ``import snowflake.connector`` inside SnowflakeEngine.__init__ first resolves
    the parent package ``snowflake`` via sys.modules.  Without this fixture the parent
    is missing and Python raises ModuleNotFoundError before the lazy-import guard can
    catch it, breaking every test that instantiates SnowflakeEngine.

    ``ProgrammingError`` and ``DatabaseError`` are real exception stubs so that
    ``except ProgrammingError`` / ``except DatabaseError`` clauses in the engine
    can actually catch instances raised during tests.
    """
    mock_sf = MagicMock(name="snowflake")
    mock_connector = MagicMock(name="snowflake.connector")
    mock_errors = MagicMock(name="snowflake.connector.errors")
    mock_errors.ProgrammingError = _SnowflakeProgrammingError
    mock_errors.DatabaseError = _SnowflakeDatabaseError
    mock_sf.connector = mock_connector
    mock_connector.errors = mock_errors
    with patch.dict(
        sys.modules,
        {
            "snowflake": mock_sf,
            "snowflake.connector": mock_connector,
            "snowflake.connector.errors": mock_errors,
        },
    ):
        yield


class TestSnowflakeEngineInit:
    """
    Test SnowflakeEngine initialization and lazy import behavior.

    Verifies that __init__ stores connection parameters without establishing
    a connection, creates a SnowflakeDialect instance, and raises helpful
    ImportError when snowflake-connector-python is not installed.
    """

    def test_init_stores_connection_params(self) -> None:
        """Should store connection parameters without creating connection."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from semolina.engines.snowflake import SnowflakeEngine

            connection_params = {
                "account": "xy12345.us-east-1",
                "user": "testuser",
                "password": "testpass",
                "warehouse": "compute_wh",
            }
            engine = SnowflakeEngine(**connection_params)

            # Connection params stored
            assert engine._connection_params == connection_params

            # No connection created at init time
            mock_connector.connect.assert_not_called()

    def test_init_creates_snowflake_dialect(self) -> None:
        """Should create SnowflakeDialect instance."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from semolina.engines.snowflake import SnowflakeEngine
            from semolina.engines.sql import SnowflakeDialect

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            assert isinstance(engine.dialect, SnowflakeDialect)

    def test_lazy_import_raises_helpful_error(self) -> None:
        """Should raise helpful ImportError when snowflake-connector-python missing."""
        from semolina.engines.snowflake import SnowflakeEngine

        # Block snowflake.connector by setting it to None in sys.modules.
        # Python raises ImportError for any blocked (None) sys.modules entry,
        # which the __init__ guard catches and re-raises with a helpful message.
        with (
            patch.dict(sys.modules, {"snowflake.connector": None}),
            pytest.raises(ImportError) as exc_info,
        ):
            SnowflakeEngine(account="test", user="user", password="pass")

        error_msg = str(exc_info.value)
        assert "snowflake-connector-python" in error_msg
        assert "pip install semolina[snowflake]" in error_msg


class TestSnowflakeEngineToSQL:
    """
    Test SnowflakeEngine.to_sql() SQL generation delegation.

    Verifies that to_sql() delegates to SQLBuilder with SnowflakeDialect,
    generates AGG() syntax for metrics, uses double quotes for identifiers,
    and properly escapes quotes in field names.
    """

    def test_to_sql_delegates_to_sqlbuilder(self) -> None:
        """Should delegate to SQLBuilder with SnowflakeDialect."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)

            with patch("semolina.engines.snowflake.SQLBuilder") as mock_builder_class:
                mock_builder = Mock()
                mock_builder.build_select.return_value = 'SELECT AGG("revenue") FROM "sales_view"'
                mock_builder_class.return_value = mock_builder

                sql = engine.to_sql(query)

                # SQLBuilder instantiated with SnowflakeDialect
                mock_builder_class.assert_called_once()
                args = mock_builder_class.call_args[0]
                from semolina.engines.sql import SnowflakeDialect

                assert isinstance(args[0], SnowflakeDialect)

                # build_select called with query
                mock_builder.build_select.assert_called_once_with(query)
                assert sql == 'SELECT AGG("revenue") FROM "sales_view"'

    def test_to_sql_generates_agg_syntax(self) -> None:
        """Should wrap metrics in AGG() with UPPERCASE column names (Snowflake normalization)."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue, Sales.cost)
            sql = engine.to_sql(query)

            # SnowflakeDialect.normalize_identifier uppercases field names
            assert 'AGG("REVENUE")' in sql
            assert 'AGG("COST")' in sql

    def test_to_sql_quotes_identifiers(self) -> None:
        """Should use double quotes for identifiers (UPPERCASE via Snowflake normalization)."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
            sql = engine.to_sql(query)

            # normalize_identifier converts Python snake_case names to UPPERCASE
            assert '"REVENUE"' in sql
            assert '"COUNTRY"' in sql
            assert '"sales_view"' in sql

    def test_to_sql_escapes_quotes(self) -> None:
        """Should escape double quotes in field names."""
        from semolina.engines.sql import SnowflakeDialect

        # Test quote escaping via dialect
        dialect = SnowflakeDialect()
        quoted = dialect.quote_identifier('my"field')
        assert quoted == '"my""field"'


class TestSnowflakeEngineExecute:
    """
    Test SnowflakeEngine.execute() with mocked Snowflake connector.

    Verifies connection lifecycle management using context managers,
    cursor execution, result mapping from tuples to dicts, and handling
    of empty results.
    """

    def test_execute_uses_context_manager_for_connection(self) -> None:
        """Should use context manager for connection lifecycle."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,)]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(
                account="xy12345.us-east-1", user="testuser", password="testpass"
            )
            query = _Query().metrics(Sales.revenue)
            engine.execute(query)

            # Verify connect called with connection params
            mock_connect.assert_called_once_with(
                account="xy12345.us-east-1", user="testuser", password="testpass"
            )

            # Verify context manager __enter__ and __exit__ called
            mock_connect.return_value.__enter__.assert_called_once()
            mock_connect.return_value.__exit__.assert_called_once()

    def test_execute_uses_context_manager_for_cursor(self) -> None:
        """Should use context manager for cursor lifecycle."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,)]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)
            engine.execute(query)

            # Verify cursor context manager
            mock_conn.cursor.assert_called_once()
            mock_conn.cursor.return_value.__enter__.assert_called_once()
            mock_conn.cursor.return_value.__exit__.assert_called_once()

    def test_execute_calls_cursor_execute_with_sql(self) -> None:
        """Should call cursor.execute with SQL from to_sql()."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,)]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)

            # Get expected SQL
            expected_sql = engine.to_sql(query)

            # Execute query
            engine.execute(query)

            # Verify cursor.execute called with correct SQL and empty params
            mock_cursor.execute.assert_called_once_with(expected_sql, [])

    def test_execute_maps_tuples_to_dicts(self) -> None:
        """Should map result tuples to dicts with correct column names."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",), ("country",)]
        mock_cursor.fetchall.return_value = [(100, "US"), (200, "CA")]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
            results = engine.execute(query)

            # Verify tuples mapped to dicts
            expected = [{"revenue": 100, "country": "US"}, {"revenue": 200, "country": "CA"}]
            assert results == expected

    def test_execute_returns_list_of_dicts(self) -> None:
        """Should return list[dict[str, Any]]."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,), (2000,)]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)
            results = engine.execute(query)

            # Verify return type
            assert isinstance(results, list)
            assert all(isinstance(row, dict) for row in results)
            assert all(isinstance(k, str) for row in results for k in row)

    def test_execute_handles_empty_results(self) -> None:
        """Should return empty list when query returns no results."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)
            results = engine.execute(query)

            assert results == []


class TestSnowflakeEngineErrorHandling:
    """
    Test SnowflakeEngine error handling and translation.

    Verifies that Snowflake ProgrammingError and DatabaseError are caught
    and translated to RuntimeError with helpful error messages, and that
    original exceptions are chained using 'from e' pattern.
    """

    def test_programming_error_translated_to_runtime_error(self) -> None:
        """Should translate ProgrammingError to RuntimeError with details."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Import ProgrammingError from snowflake.connector.errors
        from snowflake.connector.errors import (  # pyright: ignore[reportMissingImports]
            ProgrammingError,
        )

        # Create mock error with errno, sqlstate, msg attributes
        prog_error = ProgrammingError(
            msg="SQL compilation error: Object 'SALES_VIEW' does not exist",
            errno=2003,
            sqlstate="42S02",
        )
        mock_cursor.execute.side_effect = prog_error

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            error_msg = str(exc_info.value)
            assert "Snowflake query failed" in error_msg
            assert "2003" in error_msg
            assert "42S02" in error_msg
            assert "does not exist" in error_msg

    def test_database_error_translated_to_runtime_error(self) -> None:
        """Should translate DatabaseError to RuntimeError."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        from snowflake.connector.errors import (  # pyright: ignore[reportMissingImports]
            DatabaseError,
        )

        db_error = DatabaseError(msg="Connection failed: Authentication error")
        mock_cursor.execute.side_effect = db_error

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            error_msg = str(exc_info.value)
            assert "Snowflake database error" in error_msg
            assert "Authentication error" in error_msg

    def test_original_exception_chained(self) -> None:
        """Should chain original exception using 'from e' pattern."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        from snowflake.connector.errors import (  # pyright: ignore[reportMissingImports]
            ProgrammingError,
        )

        prog_error = ProgrammingError(msg="Test error", errno=1234, sqlstate="12345")
        mock_cursor.execute.side_effect = prog_error

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = _Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            # Verify __cause__ is set to original exception
            assert exc_info.value.__cause__ is prog_error


class TestSnowflakeEngineIntegration:
    """
    Test end-to-end SnowflakeEngine integration flows.

    Verifies full query execution pipeline from query creation through
    SQL generation, connection, execution, and result mapping. Tests
    multiple queries on same engine to verify connection parameter reuse.
    """

    def test_full_query_execution_flow(self) -> None:
        """Should execute complete pipeline from query to results."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",), ("cost",), ("country",)]
        mock_cursor.fetchall.return_value = [
            (1000, 100, "US"),
            (2000, 200, "CA"),
            (500, 50, "UK"),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            # Create engine
            engine = SnowflakeEngine(
                account="xy12345.us-east-1",
                user="testuser",
                password="testpass",
                warehouse="compute_wh",
            )

            # Create query
            query = (
                _Query()
                .metrics(Sales.revenue, Sales.cost)
                .dimensions(Sales.country)
                .order_by(Sales.revenue.desc())
                .limit(100)
            )

            # Execute query
            results = engine.execute(query)

            # Verify results
            assert len(results) == 3
            assert results[0] == {"revenue": 1000, "cost": 100, "country": "US"}
            assert results[1] == {"revenue": 2000, "cost": 200, "country": "CA"}
            assert results[2] == {"revenue": 500, "cost": 50, "country": "UK"}

            # Verify SQL was generated and executed
            mock_cursor.execute.assert_called_once()
            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "AGG" in executed_sql
            # SnowflakeDialect normalizes to UPPERCASE
            assert "REVENUE" in executed_sql
            assert "COUNTRY" in executed_sql

    def test_multiple_queries_same_engine(self) -> None:
        """Should reuse connection params for multiple queries."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test.us-west-2", user="testuser", password="testpass")

            # Execute first query
            mock_cursor.description = [("revenue",)]
            mock_cursor.fetchall.return_value = [(1000,)]
            query1 = _Query().metrics(Sales.revenue)
            results1 = engine.execute(query1)

            # Execute second query
            mock_cursor.description = [("cost",)]
            mock_cursor.fetchall.return_value = [(100,)]
            query2 = _Query().metrics(Sales.cost)
            results2 = engine.execute(query2)

            # Verify both queries executed
            assert results1 == [{"revenue": 1000}]
            assert results2 == [{"cost": 100}]

            # Verify connection params reused (connect called twice with same params)
            assert mock_connect.call_count == 2
            call1 = mock_connect.call_args_list[0]
            call2 = mock_connect.call_args_list[1]
            assert call1 == call2


class TestSnowflakeEngineIntrospect:
    """
    Test SnowflakeEngine.introspect() with mocked Snowflake connector.

    Verifies that introspect() executes SHOW COLUMNS IN VIEW,
    parses rows into IntrospectedView, handles kind casing, maps data_type
    JSON, populates description from comment column, and raises RuntimeError
    when the view cannot be found or accessed.
    """

    def _make_cursor_row(
        self,
        column_name: str,
        kind: str,
        data_type_dict: dict[str, object],
        comment: str = "",
    ) -> tuple[str, str, str, str]:
        """Build a mock SHOW COLUMNS row as a tuple matching the description column order."""
        return (column_name, kind, json.dumps(data_type_dict), comment)

    def _make_engine(self) -> object:
        """Create a SnowflakeEngine with a mocked connector."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from semolina.engines.snowflake import SnowflakeEngine

            return SnowflakeEngine(account="test", user="user", password="pass")

    def test_introspect_basic_metric_dimension_fact(self) -> None:
        """Should parse one metric, one dimension, one fact into IntrospectedView."""
        from semolina.codegen.introspector import IntrospectedField, IntrospectedView

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # description columns: column_name, kind, data_type, comment
        mock_cursor.description = [
            ("column_name",),
            ("kind",),
            ("data_type",),
            ("comment",),
        ]
        mock_cursor.fetchall.return_value = [
            ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
            ("country", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
            ("date_key", "FACT", json.dumps({"type": "DATE"}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("sales_view")

        assert isinstance(result, IntrospectedView)
        assert result.view_name == "sales_view"
        assert result.class_name == "SalesView"
        assert len(result.fields) == 3

        revenue = result.fields[0]
        assert isinstance(revenue, IntrospectedField)
        assert revenue.name == "revenue"
        assert revenue.field_type == "metric"
        assert revenue.data_type == "int"

        country = result.fields[1]
        assert country.name == "country"
        assert country.field_type == "dimension"
        assert country.data_type == "str"

        date_key = result.fields[2]
        assert date_key.name == "date_key"
        assert date_key.field_type == "fact"
        assert date_key.data_type == "datetime.date"

    def test_introspect_kind_lowercase_conversion(self) -> None:
        """Should lowercase uppercase METRIC/DIMENSION/FACT kind values."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("column_name",),
            ("kind",),
            ("data_type",),
            ("comment",),
        ]
        mock_cursor.fetchall.return_value = [
            ("total_sales", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
            ("region", "DIMENSION", json.dumps({"type": "TEXT"}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("report_view")

        assert result.fields[0].field_type == "metric"
        assert result.fields[1].field_type == "dimension"

    def test_introspect_fixed_scale_zero_maps_to_int(self) -> None:
        """Should map FIXED with scale=0 to 'int'."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = [
            ("count", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("count_view")

        assert result.fields[0].data_type == "int"

    def test_introspect_fixed_nonzero_scale_maps_to_float(self) -> None:
        """Should map FIXED with scale=2 to 'float'."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = [
            ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 2}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("revenue_view")

        assert result.fields[0].data_type == "float"

    def test_introspect_geography_produces_todo(self) -> None:
        """Should produce data_type starting with 'TODO:' for GEOGRAPHY type."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = [
            ("location", "DIMENSION", json.dumps({"type": "GEOGRAPHY"}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("geo_view")

        assert result.fields[0].data_type is not None
        assert result.fields[0].data_type.startswith("TODO:")

    def test_introspect_populates_description_from_comment(self) -> None:
        """Should populate field description from 'comment' column when present."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = [
            ("revenue", "METRIC", json.dumps({"type": "FIXED", "scale": 0}), "Total revenue"),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("sales_view")

        assert result.fields[0].description == "Total revenue"

    def test_introspect_executes_correct_sql(self) -> None:
        """Should execute SHOW COLUMNS IN VIEW {view_name}."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            engine.introspect("my_sales_view")

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "SHOW COLUMNS IN VIEW" in executed_sql
        assert "my_sales_view" in executed_sql

    def test_introspect_sql_uses_in_view_not_semantic_view(self) -> None:
        """
        Should use SHOW COLUMNS IN VIEW, not SHOW COLUMNS IN SEMANTIC VIEW.

        'SHOW COLUMNS IN SEMANTIC VIEW' is invalid Snowflake SQL and is rejected
        with 'syntax error ... unexpected VIEW'. The correct syntax is
        'SHOW COLUMNS IN VIEW' which works for standard, materialized, and
        semantic views alike.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            engine.introspect("my_sales_view")

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "SHOW COLUMNS IN VIEW" in executed_sql
        assert "IN SEMANTIC VIEW" not in executed_sql
        assert "my_sales_view" in executed_sql

    def test_introspect_pascal_case_class_name_simple(self) -> None:
        """Should convert snake_case view name to PascalCase class name."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("sales_revenue_view")

        assert result.class_name == "SalesRevenueView"

    def test_introspect_pascal_case_schema_qualified_name(self) -> None:
        """Should use last segment after '.' for class name derivation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("my_db.my_schema.sales_view")

        assert result.class_name == "SalesView"
        assert result.view_name == "my_db.my_schema.sales_view"

    def test_introspect_auto_qualifies_two_part_name_with_database(self) -> None:
        """
        Should prepend database to a two-part schema.view name.

        Snowflake SHOW COLUMNS IN VIEW requires a fully-qualified three-part
        identifier (database.schema.view). When the caller passes schema.view,
        introspect() must prepend the database from the connection params to
        avoid 'Must specify the full search path starting from database'.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass", database="MY_DB")
            engine.introspect("dev.sem_orders")

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "MY_DB.dev.sem_orders" in executed_sql

    def test_introspect_auto_qualifies_one_part_name_with_database(self) -> None:
        """Should prepend database to a bare view name when database is known."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass", database="MY_DB")
            engine.introspect("sem_orders")

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "MY_DB.sem_orders" in executed_sql

    def test_introspect_three_part_name_used_as_is(self) -> None:
        """Should not modify a fully-qualified three-part name even when database is set."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = []

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass", database="MY_DB")
            engine.introspect("OTHER_DB.dev.sem_orders")

        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "OTHER_DB.dev.sem_orders" in executed_sql
        assert "MY_DB" not in executed_sql

    def test_introspect_programming_error_raises_view_not_found(self) -> None:
        """Should raise SemolinaViewNotFoundError when Snowflake raises ProgrammingError."""
        from snowflake.connector.errors import (  # pyright: ignore[reportMissingImports]
            ProgrammingError,
        )

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = ProgrammingError(
            msg="Semantic view 'nonexistent_view' does not exist",
            errno=2003,
            sqlstate="42S02",
        )

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.base import SemolinaViewNotFoundError
            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")

            with pytest.raises(SemolinaViewNotFoundError) as exc_info:
                engine.introspect("nonexistent_view")

            assert "Snowflake view not found or inaccessible" in str(exc_info.value)

    def test_introspect_database_error_raises_connection_error(self) -> None:
        """Should raise SemolinaConnectionError when Snowflake raises DatabaseError."""
        from snowflake.connector.errors import (  # pyright: ignore[reportMissingImports]
            DatabaseError,
        )

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = DatabaseError(msg="Connection failure")

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.base import SemolinaConnectionError
            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")

            with pytest.raises(SemolinaConnectionError) as exc_info:
                engine.introspect("sales_view")

            assert "Snowflake connection failed" in str(exc_info.value)

    def test_introspect_uppercase_column_lowercased_no_source_name(self) -> None:
        """
        Standard UPPERCASE column (ORDER_ID) → name='order_id', source_name=None.

        For standard Snowflake columns stored as UPPERCASE, the Python field name
        is the lowercased version. normalize_identifier('order_id') → 'ORDER_ID'
        round-trips correctly, so source_name is not needed.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = [
            ("ORDER_ID", "DIMENSION", json.dumps({"type": "FIXED", "scale": 0}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("orders_view")

        field = result.fields[0]
        assert field.name == "order_id"
        assert field.source_name is None

    def test_introspect_quoted_lowercase_column_gets_source_name(self) -> None:
        """
        Quoted-lowercase column ('order_id') → name='order_id', source_name='order_id'.

        When a Snowflake column was created with a quoted identifier ("order_id"),
        it is stored as-is (lowercase). python_name.upper() = 'ORDER_ID' != 'order_id',
        so source_name is set to the original column name to preserve round-tripping.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("column_name",), ("kind",), ("data_type",), ("comment",)]
        mock_cursor.fetchall.return_value = [
            ("order_id", "DIMENSION", json.dumps({"type": "FIXED", "scale": 0}), ""),
        ]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from semolina.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            result = engine.introspect("orders_view")

        field = result.fields[0]
        assert field.name == "order_id"
        assert field.source_name == "order_id"
