"""
Comprehensive unit tests for DatabricksEngine using unittest.mock.

Tests cover:
- Lazy import and initialization
- SQL generation delegation to SQLBuilder
- Connection lifecycle with context managers
- Result mapping from tuples to dicts
- Error handling and translation
- End-to-end integration flows
- Unity Catalog three-part naming

All tests use unittest.mock to simulate Databricks connector behavior without
requiring actual Databricks workspace access.
"""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from conftest import Sales

from cubano.query import Query


def _create_mock_databricks() -> tuple[MagicMock, MagicMock, MagicMock]:
    """
    Create a properly structured mock for databricks.sql module.

    Returns:
        Tuple of (mock_databricks, mock_sql, mock_exc)
    """
    DatabaseError = type("DatabaseError", (Exception,), {})
    OperationalError = type("OperationalError", (Exception,), {})
    Error = type("Error", (Exception,), {})

    mock_exc = MagicMock()
    mock_exc.DatabaseError = DatabaseError
    mock_exc.OperationalError = OperationalError
    mock_exc.Error = Error

    mock_sql = MagicMock()
    mock_sql.exc = mock_exc

    mock_databricks = MagicMock()
    mock_databricks.sql = mock_sql

    return mock_databricks, mock_sql, mock_exc


class TestDatabricksEngineInit:
    """
    Test DatabricksEngine initialization and lazy import behavior.

    Verifies that __init__ stores connection parameters without establishing
    a connection, creates a DatabricksDialect instance, and raises helpful
    ImportError when databricks-sql-connector is not installed.
    """

    def test_init_stores_connection_params(self) -> None:
        """Should store connection parameters without creating connection."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine

            connection_params = {
                "server_hostname": "workspace.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/abc123",
                "access_token": "dapi...",
            }
            engine = DatabricksEngine(**connection_params)

            # Connection params stored
            assert engine._connection_params == connection_params

            # No connection created at init time
            mock_connector.connect.assert_not_called()

    def test_init_creates_databricks_dialect(self) -> None:
        """Should create DatabricksDialect instance."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine
            from cubano.engines.sql import DatabricksDialect

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            assert isinstance(engine.dialect, DatabricksDialect)

    def test_lazy_import_raises_helpful_error(self) -> None:
        """Should raise helpful ImportError when databricks-sql-connector missing."""
        import builtins
        import sys

        # First import DatabricksEngine with databricks.sql available
        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine

        # Now remove databricks.sql and test __init__ behavior
        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "databricks.sql":
                raise ImportError("No module named 'databricks.sql'")
            return original_import(name, *args, **kwargs)  # type: ignore[reportUnknownArgumentType]

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError) as exc_info:
                DatabricksEngine(
                    server_hostname="test",
                    http_path="/sql/1.0/warehouses/abc",
                    access_token="token",
                )

            error_msg = str(exc_info.value)
            assert "databricks-sql-connector" in error_msg
            assert "pip install cubano[databricks]" in error_msg


class TestDatabricksEngineToSQL:
    """
    Test DatabricksEngine.to_sql() SQL generation delegation.

    Verifies that to_sql() delegates to SQLBuilder with DatabricksDialect,
    generates MEASURE() syntax for metrics, uses backticks for identifiers,
    and properly escapes backticks in field names.
    """

    def test_to_sql_delegates_to_sqlbuilder(self) -> None:
        """Should delegate to SQLBuilder with DatabricksDialect."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)

            with patch("cubano.engines.databricks.SQLBuilder") as mock_builder_class:
                mock_builder = Mock()
                expected_sql = "SELECT MEASURE(`revenue`) FROM `sales_view`"
                mock_builder.build_select.return_value = expected_sql
                mock_builder_class.return_value = mock_builder

                sql = engine.to_sql(query)

                # SQLBuilder instantiated with DatabricksDialect
                mock_builder_class.assert_called_once()
                args = mock_builder_class.call_args[0]
                from cubano.engines.sql import DatabricksDialect

                assert isinstance(args[0], DatabricksDialect)

                # build_select called with query
                mock_builder.build_select.assert_called_once_with(query)
                assert sql == expected_sql

    def test_to_sql_generates_measure_syntax(self) -> None:
        """Should wrap metrics in MEASURE()."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue, Sales.cost)
            sql = engine.to_sql(query)

            assert "MEASURE(`revenue`)" in sql
            assert "MEASURE(`cost`)" in sql

    def test_to_sql_quotes_identifiers_with_backticks(self) -> None:
        """Should use backticks for identifier quoting."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue).dimensions(Sales.country)
            sql = engine.to_sql(query)

            assert "`revenue`" in sql
            assert "`country`" in sql
            assert "`sales_view`" in sql

    def test_to_sql_escapes_backticks(self) -> None:
        """Should escape backticks in field names."""
        from cubano.engines.sql import DatabricksDialect

        # Test backtick escaping via dialect
        dialect = DatabricksDialect()
        quoted = dialect.quote_identifier("my`field")
        assert quoted == "`my``field`"

    def test_to_sql_handles_unity_catalog_three_part_names(self) -> None:
        """Should handle Unity Catalog three-part names with backtick quoting."""
        import sys

        mock_connector = MagicMock()
        with patch.dict(sys.modules, {"databricks.sql": mock_connector}):
            from cubano.engines.databricks import DatabricksEngine

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )

            # Create a query using a Unity Catalog three-part name
            from cubano import Dimension, Metric, SemanticView

            class UnityView(SemanticView, view="main.analytics.sales_view"):
                """Semantic view with Unity Catalog three-part name."""

                revenue = Metric()
                country = Dimension()

            query = Query().metrics(UnityView.revenue).dimensions(UnityView.country)
            sql = engine.to_sql(query)

            # Should have backtick-quoted three-part name (as single quoted string or separated)
            assert "main" in sql and "analytics" in sql and "sales_view" in sql
            assert "`" in sql  # Should use backticks for quoting


class TestDatabricksEngineExecute:
    """
    Test DatabricksEngine.execute() with mocked Databricks connector.

    Verifies connection lifecycle management using context managers,
    cursor execution, result mapping from tuples to dicts, and handling
    of empty results.
    """

    def test_execute_uses_context_manager_for_connection(self) -> None:
        """Should use context manager for connection lifecycle."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,)]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)
            engine.execute(query)

            # Verify connect called with connection params
            mock_sql.connect.assert_called_once_with(
                server_hostname="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )

            # Verify context manager __enter__ and __exit__ called
            mock_sql.connect.return_value.__enter__.assert_called_once()
            mock_sql.connect.return_value.__exit__.assert_called_once()

    def test_execute_uses_context_manager_for_cursor(self) -> None:
        """Should use context manager for cursor lifecycle."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,)]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)
            engine.execute(query)

            # Verify cursor context manager
            mock_conn.cursor.assert_called_once()
            mock_conn.cursor.return_value.__enter__.assert_called_once()
            mock_conn.cursor.return_value.__exit__.assert_called_once()

    def test_execute_calls_cursor_execute_with_sql(self) -> None:
        """Should call cursor.execute with SQL from to_sql()."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,)]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)

            # Get expected SQL
            expected_sql = engine.to_sql(query)

            # Execute query
            engine.execute(query)

            # Verify cursor.execute called with correct SQL
            mock_cursor.execute.assert_called_once_with(expected_sql)

    def test_execute_maps_tuples_to_dicts(self) -> None:
        """Should map result tuples to dicts with correct column names."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",), ("country",)]
        mock_cursor.fetchall.return_value = [(100, "US"), (200, "CA")]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue).dimensions(Sales.country)
            results = engine.execute(query)

            # Verify tuples mapped to dicts
            expected = [{"revenue": 100, "country": "US"}, {"revenue": 200, "country": "CA"}]
            assert results == expected

    def test_execute_returns_list_of_dicts(self) -> None:
        """Should return list[dict[str, Any]]."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = [(1000,), (2000,)]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)
            results = engine.execute(query)

            # Verify return type
            assert isinstance(results, list)
            assert all(isinstance(row, dict) for row in results)
            assert all(isinstance(k, str) for row in results for k in row)

    def test_execute_handles_empty_results(self) -> None:
        """Should return empty list when query returns no results."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",)]
        mock_cursor.fetchall.return_value = []

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)
            results = engine.execute(query)

            assert results == []


class TestDatabricksEngineErrorHandling:
    """
    Test DatabricksEngine error handling and translation.

    Verifies that Databricks DatabaseError, OperationalError, and Error
    are caught and translated to RuntimeError with helpful error messages,
    and that original exceptions are chained using 'from e' pattern.
    """

    def test_database_error_translated_to_runtime_error(self) -> None:
        """Should translate DatabaseError to RuntimeError with details."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()
        DatabaseError = mock_exc.DatabaseError

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        db_error = DatabaseError("Object 'SALES_VIEW' does not exist or is not a semantic view")
        mock_cursor.execute.side_effect = db_error

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            error_msg = str(exc_info.value)
            assert "Databricks query failed" in error_msg
            assert "does not exist" in error_msg

    def test_operational_error_translated_to_runtime_error(self) -> None:
        """Should translate OperationalError to RuntimeError."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()
        OperationalError = mock_exc.OperationalError

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        op_error = OperationalError("Connection failed: Authentication error")
        mock_cursor.execute.side_effect = op_error

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            error_msg = str(exc_info.value)
            assert "Databricks operational error" in error_msg
            assert "Authentication error" in error_msg

    def test_generic_error_translated_to_runtime_error(self) -> None:
        """Should translate generic Error to RuntimeError."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()
        Error = mock_exc.Error

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        error = Error("Generic Databricks error")
        mock_cursor.execute.side_effect = error

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            error_msg = str(exc_info.value)
            assert "Databricks error" in error_msg

    def test_original_exception_chained(self) -> None:
        """Should chain original exception using 'from e' pattern."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()
        DatabaseError = mock_exc.DatabaseError

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        original_error = DatabaseError("Test error")
        mock_cursor.execute.side_effect = original_error

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="test",
                http_path="/sql/1.0/warehouses/abc",
                access_token="token",
            )
            query = Query().metrics(Sales.revenue)

            with pytest.raises(RuntimeError) as exc_info:
                engine.execute(query)

            # Verify __cause__ is set to original exception
            assert exc_info.value.__cause__ is original_error


class TestDatabricksEngineIntegration:
    """
    Test end-to-end DatabricksEngine integration flows.

    Verifies full query execution pipeline from query creation through
    SQL generation, connection, execution, and result mapping. Tests
    multiple queries on same engine to verify connection parameter reuse
    and Unity Catalog scenarios.
    """

    def test_full_query_execution_flow(self) -> None:
        """Should execute complete pipeline from query to results."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",), ("cost",), ("country",)]
        mock_cursor.fetchall.return_value = [
            (1000, 100, "US"),
            (2000, 200, "CA"),
            (500, 50, "UK"),
        ]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Create engine
            engine = DatabricksEngine(
                server_hostname="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                access_token="dapi...",
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
            assert "MEASURE" in executed_sql
            assert "revenue" in executed_sql
            assert "country" in executed_sql

    def test_multiple_queries_same_engine(self) -> None:
        """Should reuse connection params for multiple queries."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            engine = DatabricksEngine(
                server_hostname="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                access_token="dapi...",
            )

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
            assert mock_sql.connect.call_count == 2
            call1 = mock_sql.connect.call_args_list[0]
            call2 = mock_sql.connect.call_args_list[1]
            assert call1 == call2

    def test_unity_catalog_three_part_name_query(self) -> None:
        """Should execute queries with Unity Catalog three-part names."""
        mock_databricks, mock_sql, mock_exc = _create_mock_databricks()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("revenue",), ("country",)]
        mock_cursor.fetchall.return_value = [(1000, "US"), (2000, "CA")]

        with patch.dict(
            sys.modules,
            {
                "databricks": mock_databricks,
                "databricks.sql": mock_sql,
                "databricks.sql.exc": mock_exc,
            },
        ):
            from cubano import Dimension, Metric, SemanticView
            from cubano.engines.databricks import DatabricksEngine

            mock_sql.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Create engine
            engine = DatabricksEngine(
                server_hostname="workspace.cloud.databricks.com",
                http_path="/sql/1.0/warehouses/abc123",
                access_token="dapi...",
                catalog="main",
                schema="analytics",
            )

            # Define semantic view with three-part name
            class UnityView(SemanticView, view="main.analytics.sales_view"):
                """Unity Catalog semantic view with three-part name."""

                revenue = Metric()
                country = Dimension()

            # Create and execute query
            query = Query().metrics(UnityView.revenue).dimensions(UnityView.country)
            results = engine.execute(query)

            # Verify results
            assert len(results) == 2
            assert results[0] == {"revenue": 1000, "country": "US"}
            assert results[1] == {"revenue": 2000, "country": "CA"}

            # Verify SQL includes three-part name (as single quoted string or separated)
            mock_cursor.execute.assert_called_once()
            executed_sql = mock_cursor.execute.call_args[0][0]
            assert "main" in executed_sql
            assert "analytics" in executed_sql
            assert "sales_view" in executed_sql
