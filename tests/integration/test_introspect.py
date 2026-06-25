"""
Warehouse introspection integration test (pytest-adbc-replay).

Validates :meth:`DatabricksEngine.introspect` end-to-end over the real ADBC
pool: ``DESCRIBE TABLE EXTENDED {view} AS JSON`` against the ``sales_view``
metric view the recording fixture builds. Runs against a recorded cassette by
default (incl. CI, no credentials); re-record with::

    pytest --adbc-record=once tests/integration/test_introspect.py

Databricks-only: Snowflake and DuckDB introspection use different metadata
statements (``SHOW COLUMNS IN VIEW`` / ``DESCRIBE SEMANTIC VIEW``) and are
covered by their own engine unit tests.

See docs/src/how-to/warehouse-testing.rst for the full record/replay workflow.
"""

from __future__ import annotations

from typing import Any

import pytest

# Records/replays an ADBC cassette; the plugin intercepts the pool's connection.
pytestmark = pytest.mark.adbc_cassette


def test_databricks_introspect_metric_view(databricks_engine: Any) -> None:
    """DESCRIBE TABLE EXTENDED AS JSON over ADBC -> IntrospectedView."""
    view = databricks_engine.introspect("sales_view")

    assert view.view_name == "sales_view"
    assert view.class_name == "SalesView"

    by_name = {field.name: field for field in view.fields}
    assert set(by_name) == {"country", "region", "revenue", "cost"}

    # is_measure -> metric; everything else -> dimension. type.name -> Python type.
    assert by_name["country"].field_type == "dimension"
    assert by_name["country"].data_type == "str"
    assert by_name["region"].field_type == "dimension"
    assert by_name["region"].data_type == "str"
    assert by_name["revenue"].field_type == "metric"
    assert by_name["revenue"].data_type == "int"
    assert by_name["cost"].field_type == "metric"
    assert by_name["cost"].data_type == "int"

    # The fixture view sets no column comments and uses round-tripping names.
    assert by_name["country"].description == ""
    assert by_name["country"].source_name is None
