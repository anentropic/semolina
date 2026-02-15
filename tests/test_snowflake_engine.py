"""
Comprehensive unit tests for SnowflakeEngine using unittest.mock.

Tests cover:
- Lazy import and initialization
- SQL generation delegation to SQLBuilder
- Connection lifecycle with context managers
- Result mapping from tuples to dicts
- Error handling and translation
- End-to-end integration flows

All tests use unittest.mock to simulate Snowflake connector behavior without
requiring actual Snowflake warehouse access.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from conftest import Sales

from cubano.query import Query


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
            from cubano.engines.snowflake import SnowflakeEngine

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
            from cubano.engines.snowflake import SnowflakeEngine
            from cubano.engines.sql import SnowflakeDialect

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            assert isinstance(engine.dialect, SnowflakeDialect)

    def test_lazy_import_raises_helpful_error(self) -> None:
        """Should raise helpful ImportError when snowflake-connector-python missing."""
        import builtins
        import sys

        # First import SnowflakeEngine with snowflake.connector available
        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from cubano.engines.snowflake import SnowflakeEngine

        # Now remove snowflake.connector and test __init__ behavior
        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "snowflake.connector":
                raise ImportError("No module named 'snowflake.connector'")
            return original_import(name, *args, **kwargs)  # type: ignore[reportUnknownArgumentType]

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError) as exc_info:
                SnowflakeEngine(account="test", user="user", password="pass")

            error_msg = str(exc_info.value)
            assert "snowflake-connector-python" in error_msg
            assert "pip install cubano[snowflake]" in error_msg


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
            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)

            with patch("cubano.engines.snowflake.SQLBuilder") as mock_builder_class:
                mock_builder = Mock()
                mock_builder.build_select.return_value = 'SELECT AGG("revenue") FROM "sales_view"'
                mock_builder_class.return_value = mock_builder

                sql = engine.to_sql(query)

                # SQLBuilder instantiated with SnowflakeDialect
                mock_builder_class.assert_called_once()
                args = mock_builder_class.call_args[0]
                from cubano.engines.sql import SnowflakeDialect

                assert isinstance(args[0], SnowflakeDialect)

                # build_select called with query
                mock_builder.build_select.assert_called_once_with(query)
                assert sql == 'SELECT AGG("revenue") FROM "sales_view"'

    def test_to_sql_generates_agg_syntax(self) -> None:
        """Should wrap metrics in AGG()."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue, Sales.cost)
            sql = engine.to_sql(query)

            assert 'AGG("revenue")' in sql
            assert 'AGG("cost")' in sql

    def test_to_sql_quotes_identifiers(self) -> None:
        """Should use double quotes for identifiers."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"snowflake.connector": mock_connector}):
            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue).dimensions(Sales.country)
            sql = engine.to_sql(query)

            assert '"revenue"' in sql
            assert '"country"' in sql
            assert '"sales_view"' in sql

    def test_to_sql_escapes_quotes(self) -> None:
        """Should escape double quotes in field names."""
        from cubano.engines.sql import SnowflakeDialect

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

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(
                account="xy12345.us-east-1", user="testuser", password="testpass"
            )
            query = Query().metrics(Sales.revenue)
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

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)
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

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)

            # Get expected SQL
            expected_sql = engine.to_sql(query)

            # Execute query
            engine.execute(query)

            # Verify cursor.execute called with correct SQL
            mock_cursor.execute.assert_called_once_with(expected_sql)

    def test_execute_maps_tuples_to_dicts(self) -> None:
        """Should map result tuples to dicts with correct column names."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",), ("country",)]
        mock_cursor.fetchall.return_value = [(100, "US"), (200, "CA")]

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue).dimensions(Sales.country)
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

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)
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

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)
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
        from snowflake.connector.errors import ProgrammingError

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

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)

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

        from snowflake.connector.errors import DatabaseError

        db_error = DatabaseError(msg="Connection failed: Authentication error")
        mock_cursor.execute.side_effect = db_error

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            error_msg = str(exc_info.value)
            assert "Snowflake database error" in error_msg
            assert "Authentication error" in error_msg

    def test_original_exception_chained(self) -> None:
        """Should chain original exception using 'from e' pattern."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        from snowflake.connector.errors import ProgrammingError

        prog_error = ProgrammingError(msg="Test error", errno=1234, sqlstate="12345")
        mock_cursor.execute.side_effect = prog_error

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test", user="user", password="pass")
            query = Query().metrics(Sales.revenue)

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

            from cubano.engines.snowflake import SnowflakeEngine

            # Create engine
            engine = SnowflakeEngine(
                account="xy12345.us-east-1",
                user="testuser",
                password="testpass",
                warehouse="compute_wh",
            )

            # Create query
            query = (
                Query()
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
            assert "revenue" in executed_sql
            assert "country" in executed_sql

    def test_multiple_queries_same_engine(self) -> None:
        """Should reuse connection params for multiple queries."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        with patch("snowflake.connector.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            from cubano.engines.snowflake import SnowflakeEngine

            engine = SnowflakeEngine(account="test.us-west-2", user="testuser", password="testpass")

            # Execute first query
            mock_cursor.description = [("revenue",)]
            mock_cursor.fetchall.return_value = [(1000,)]
            query1 = Query().metrics(Sales.revenue)
            results1 = engine.execute(query1)

            # Execute second query
            mock_cursor.description = [("cost",)]
            mock_cursor.fetchall.return_value = [(100,)]
            query2 = Query().metrics(Sales.cost)
            results2 = engine.execute(query2)

            # Verify both queries executed
            assert results1 == [{"revenue": 1000}]
            assert results2 == [{"cost": 100}]

            # Verify connection params reused (connect called twice with same params)
            assert mock_connect.call_count == 2
            call1 = mock_connect.call_args_list[0]
            call2 = mock_connect.call_args_list[1]
            assert call1 == call2
