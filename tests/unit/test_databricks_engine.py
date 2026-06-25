"""
Unit tests for DatabricksEngine on the Phase 44 Engine API.

Phase 44 moves every backend onto the ``create_engine`` / ADBC-pool contract:
the engine is built with ``create_engine(DatabricksConfig(...))`` (D1), owns one
ADBC pool plus the Databricks dialect, and executes queries through the
inherited :meth:`~semolina.engines.base.Engine.execute` pool path.

These tests assert the new-API construction, the dialect selection, SQL
generation, and ``introspect()``: its parsing of ``DESCRIBE TABLE EXTENDED ...
AS JSON`` and its ADBC error translation, over a mocked cursor. The real ADBC
introspection path is validated end-to-end against a recorded cassette in
``tests/integration/test_introspect.py``.

The mocks are deliberately untyped (``MagicMock`` pool / cursor and a patched
``connect()``), so the per-rule scope-disable below keeps basedpyright strict
quiet on the mock seam without a ``# type: ignore``.
"""
# Test-only mock seam: MagicMock pool/cursor and patch.object(engine, "connect")
# are untyped by construction. Scope-disable the rules the mock seam triggers
# under basedpyright strict (intentionally not a `# type: ignore`).
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from models import Sales

from semolina.query import _Query


def _make_databricks_engine(**overrides: Any) -> Any:
    """
    Build a DatabricksEngine via the Phase 44 ``create_engine`` factory.

    The engine owns an ADBC pool (mocked at ``create_pool`` below) plus the
    Databricks dialect derived from the config type. Tests then patch
    ``engine.connect`` to drive execution through a mocked ADBC cursor.
    """
    from adbc_poolhouse import DatabricksConfig
    from pydantic import SecretStr

    from semolina.config import create_engine

    params: dict[str, Any] = {
        "host": "workspace.cloud.databricks.com",
        "http_path": "/sql/1.0/warehouses/abc123",
        "token": SecretStr("dapi-test-token"),
    }
    params.update(overrides)
    # Avoid a live ADBC connect: create_pool returns a mock pool. The Engine
    # still owns it; execution is driven through engine.connect() below.
    with patch("semolina.config.create_pool", return_value=MagicMock(name="pool")):
        return create_engine(DatabricksConfig(**params))


def _patch_connect(engine: Any, cursor: Any) -> Any:
    """
    Patch ``engine.connect()`` to return a connection whose cursor is ``cursor``.

    Mirrors the real ADBC checkout seam used by
    :meth:`~semolina.engines.base.Engine.execute`: ``conn = self.connect()``
    then ``conn.cursor()`` (``connect()`` returns the pooled connection
    directly, not a context manager).
    """
    conn = MagicMock(name="conn")
    conn.cursor.return_value = cursor
    return patch.object(engine, "connect", return_value=conn)


class TestDatabricksEngineConstruction:
    """
    DatabricksEngine is built via create_engine and owns pool + dialect.

    Verifies the Phase 44 construction contract: create_engine selects the
    DatabricksEngine subclass, supplies the ADBC pool and the DatabricksDialect,
    and never connects at construction time.
    """

    def test_create_engine_returns_databricks_engine(self) -> None:
        """Should build a DatabricksEngine from a DatabricksConfig."""
        from semolina.engines.databricks import DatabricksEngine

        engine = _make_databricks_engine()
        assert isinstance(engine, DatabricksEngine)

    def test_engine_uses_databricks_dialect(self) -> None:
        """Should attach a DatabricksDialect derived from the config type."""
        from semolina.engines.sql import DatabricksDialect

        engine = _make_databricks_engine()
        assert isinstance(engine.dialect, DatabricksDialect)

    def test_engine_owns_pool_without_connecting(self) -> None:
        """Should hold the pool without checking out a connection at build time."""
        engine = _make_databricks_engine()
        # The mock pool is owned but connect() is not called during construction.
        engine._pool.connect.assert_not_called()  # noqa: SLF001  (test inspects owned pool)


class TestDatabricksEngineSQLGeneration:
    """
    DatabricksEngine generates SQL via its Databricks dialect builder.

    Phase 44 removed the per-engine ``to_sql`` shim; SQL is built through
    ``engine.dialect.create_builder().build_select_with_params``. Verifies
    MEASURE() wrapping for metrics and backtick identifier quoting.
    """

    def _build_sql(self, engine: Any, query: _Query) -> str:
        """Build the SELECT SQL the engine would execute for ``query``."""
        sql, _params = engine.dialect.create_builder().build_select_with_params(query)
        return sql

    def test_generates_measure_syntax(self) -> None:
        """Should wrap metrics in MEASURE()."""
        engine = _make_databricks_engine()
        query = _Query().metrics(Sales.revenue, Sales.cost)
        sql = self._build_sql(engine, query)

        assert "MEASURE(`revenue`)" in sql
        assert "MEASURE(`cost`)" in sql

    def test_quotes_identifiers_with_backticks(self) -> None:
        """Should use backticks for identifier quoting."""
        engine = _make_databricks_engine()
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        sql = self._build_sql(engine, query)

        assert "`revenue`" in sql
        assert "`country`" in sql
        assert "`sales_view`" in sql

    def test_dialect_escapes_backticks(self) -> None:
        """Should escape backticks in field names."""
        from semolina.engines.sql import DatabricksDialect

        dialect = DatabricksDialect()
        assert dialect.quote_identifier("my`field") == "`my``field`"


class TestDatabricksEngineExecute:
    """
    DatabricksEngine.execute runs through the inherited ADBC pool path.

    Verifies that execution checks a connection out of the owned pool, runs the
    generated SQL through the ADBC cursor, and maps result rows -- using the
    base Engine.execute path (no native databricks.sql connector).
    """

    def test_execute_runs_sql_over_pooled_cursor(self) -> None:
        """Should execute generated SQL through the ADBC cursor from connect()."""
        engine = _make_databricks_engine()

        cursor = MagicMock(name="cursor")
        with _patch_connect(engine, cursor):
            query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
            expected_sql, expected_params = (
                engine.dialect.create_builder().build_select_with_params(query)
            )
            engine.execute(query)

        cursor.execute.assert_called_once_with(expected_sql, expected_params)

    def test_execute_returns_semolina_cursor(self) -> None:
        """Should wrap the post-execute ADBC cursor in a SemolinaCursor."""
        from semolina.cursor import SemolinaCursor

        engine = _make_databricks_engine()

        cursor = MagicMock(name="cursor")
        with _patch_connect(engine, cursor):
            query = _Query().metrics(Sales.revenue)
            result = engine.execute(query)

        assert isinstance(result, SemolinaCursor)


def _patch_introspect_cursor(engine: Any, cursor: Any) -> Any:
    """
    Patch ``engine.connect()`` for the ``with self.connect() as conn`` seam.

    Unlike :func:`_patch_connect` (used by ``execute()``, which calls
    ``connect()`` directly), :meth:`DatabricksEngine.introspect` uses
    ``connect()`` as a context manager, so the mock's ``__enter__`` must yield a
    connection whose ``cursor()`` returns ``cursor``.
    """
    conn = MagicMock(name="conn")
    conn.cursor.return_value = cursor
    connect_cm = MagicMock(name="connect_cm")
    connect_cm.__enter__.return_value = conn
    return patch.object(engine, "connect", return_value=connect_cm)


class TestDatabricksEngineIntrospect:
    """
    DatabricksEngine.introspect parses DESCRIBE TABLE EXTENDED ... AS JSON.

    These tests drive the JSON parsing and ADBC error translation over a mocked
    cursor. The real ADBC path is validated end-to-end against a recorded
    cassette in ``tests/integration/test_introspect.py``.
    """

    # Representative payload: two string dimensions and two bigint measures
    # (``is_measure``), as Databricks returns for a metric view.
    _DESCRIBE_JSON = json.dumps(
        {
            "columns": [
                {"name": "country", "type": {"name": "string", "collation": "UTF8_BINARY"}},
                {"name": "region", "type": {"name": "string"}},
                {"name": "revenue", "type": {"name": "bigint"}, "is_measure": True},
                {"name": "cost", "type": {"name": "bigint"}, "is_measure": True},
            ]
        }
    )

    def _introspect(self, engine: Any, payload: str, view: str = "sales_view") -> Any:
        """Run introspect() with a cursor whose fetchone() returns ``payload``."""
        cursor = MagicMock(name="cursor")
        cursor.fetchone.return_value = (payload,)
        with _patch_introspect_cursor(engine, cursor):
            return engine.introspect(view)

    def test_parses_dimensions_and_measures(self) -> None:
        """is_measure -> metric, everything else -> dimension; view -> class name."""
        engine = _make_databricks_engine()
        view = self._introspect(engine, self._DESCRIBE_JSON)

        assert view.view_name == "sales_view"
        assert view.class_name == "SalesView"
        roles = {f.name: f.field_type for f in view.fields}
        assert roles == {
            "country": "dimension",
            "region": "dimension",
            "revenue": "metric",
            "cost": "metric",
        }

    def test_maps_types_to_python(self) -> None:
        """type.name -> Python annotation via databricks_type_to_python."""
        engine = _make_databricks_engine()
        view = self._introspect(engine, self._DESCRIBE_JSON)

        types = {f.name: f.data_type for f in view.fields}
        assert types == {"country": "str", "region": "str", "revenue": "int", "cost": "int"}

    def test_unmapped_type_becomes_todo(self) -> None:
        """A type with no clean Python equivalent yields a TODO placeholder."""
        payload = json.dumps({"columns": [{"name": "geo", "type": {"name": "geography"}}]})
        engine = _make_databricks_engine()
        view = self._introspect(engine, payload)

        assert view.fields[0].data_type == "TODO: geography"

    def test_non_round_tripping_name_sets_source_name(self) -> None:
        """A mixed-case column name preserves the exact warehouse name in source_name."""
        payload = json.dumps(
            {"columns": [{"name": "MyMetric", "type": {"name": "bigint"}, "is_measure": True}]}
        )
        engine = _make_databricks_engine()
        view = self._introspect(engine, payload)

        assert view.fields[0].name == "mymetric"
        assert view.fields[0].source_name == "MyMetric"

    def test_view_not_found_raises_semolina_error(self) -> None:
        """ADBC ProgrammingError -> SemolinaViewNotFoundError."""
        pytest.importorskip("adbc_driver_manager")
        from adbc_driver_manager import (  # pyright: ignore[reportMissingImports]
            AdbcStatusCode,
            ProgrammingError,
        )

        from semolina.engines.base import SemolinaViewNotFoundError

        engine = _make_databricks_engine()
        cursor = MagicMock(name="cursor")
        cursor.execute.side_effect = ProgrammingError(
            "Table or view 'missing_view' not found",
            status_code=AdbcStatusCode.NOT_FOUND,
        )
        with _patch_introspect_cursor(engine, cursor), pytest.raises(SemolinaViewNotFoundError):
            engine.introspect("missing_view")

    def test_connection_error_raises_semolina_error(self) -> None:
        """ADBC OperationalError -> SemolinaConnectionError."""
        pytest.importorskip("adbc_driver_manager")
        from adbc_driver_manager import (  # pyright: ignore[reportMissingImports]
            AdbcStatusCode,
            OperationalError,
        )

        from semolina.engines.base import SemolinaConnectionError

        engine = _make_databricks_engine()
        cursor = MagicMock(name="cursor")
        cursor.execute.side_effect = OperationalError(
            "connection failed",
            status_code=AdbcStatusCode.IO,
        )
        with _patch_introspect_cursor(engine, cursor), pytest.raises(SemolinaConnectionError):
            engine.introspect("sales_view")
