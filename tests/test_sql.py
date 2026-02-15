"""
Tests for SQL generation with Dialect and SQLBuilder classes.

Tests cover:
- SQL-01: Query.to_sql() generates valid SQL
- SQL-02: SnowflakeDialect uses double quotes and AGG() wrapping
- SQL-03: DatabricksDialect uses backticks and MEASURE() wrapping
- SQL-04: GROUP BY ALL for automatic dimension derivation
- SQL-05: Proper identifier quoting and escaping
"""

import pytest

from cubano import Dimension, Fact, Metric
from cubano.engines.sql import (
    DatabricksDialect,
    MockDialect,
    SnowflakeDialect,
    SQLBuilder,
)
from cubano.fields import NullsOrdering
from cubano.query import Query
from conftest import Sales


class TestSnowflakeDialect:
    """Test SnowflakeDialect identifier quoting and metric wrapping."""

    def test_quote_identifier_simple(self):
        """Should quote simple identifiers with double quotes."""
        dialect = SnowflakeDialect()
        assert dialect.quote_identifier("simple_name") == '"simple_name"'

    def test_quote_identifier_preserves_case(self):
        """Should preserve case exactly in quoted identifiers."""
        dialect = SnowflakeDialect()
        assert dialect.quote_identifier("REVENUE") == '"REVENUE"'
        assert dialect.quote_identifier("Revenue") == '"Revenue"'

    def test_quote_identifier_escapes_quotes(self):
        """Should escape internal double quotes by doubling them."""
        dialect = SnowflakeDialect()
        assert dialect.quote_identifier('name"with"quotes') == '"name""with""quotes"'
        assert dialect.quote_identifier('single"quote') == '"single""quote"'

    def test_quote_identifier_multiple_quotes(self):
        """Should handle multiple consecutive quotes."""
        dialect = SnowflakeDialect()
        assert dialect.quote_identifier('a""b') == '"a""""b"'

    def test_wrap_metric_simple(self):
        """Should wrap simple metric with AGG()."""
        dialect = SnowflakeDialect()
        assert dialect.wrap_metric("revenue") == 'AGG("revenue")'

    def test_wrap_metric_with_special_chars(self):
        """Should wrap metric with special characters, escaping as needed."""
        dialect = SnowflakeDialect()
        assert dialect.wrap_metric('revenue"2024') == 'AGG("revenue""2024")'

    def test_wrap_metric_uppercase(self):
        """Should preserve case in wrapped metrics."""
        dialect = SnowflakeDialect()
        assert dialect.wrap_metric("REVENUE") == 'AGG("REVENUE")'


class TestDatabricksDialect:
    """Test DatabricksDialect identifier quoting and metric wrapping."""

    def test_quote_identifier_simple(self):
        """Should quote simple identifiers with backticks."""
        dialect = DatabricksDialect()
        assert dialect.quote_identifier("simple_name") == "`simple_name`"

    def test_quote_identifier_preserves_case(self):
        """Should preserve case exactly in quoted identifiers."""
        dialect = DatabricksDialect()
        assert dialect.quote_identifier("REVENUE") == "`REVENUE`"
        assert dialect.quote_identifier("Revenue") == "`Revenue`"

    def test_quote_identifier_escapes_backticks(self):
        """Should escape internal backticks by doubling them."""
        dialect = DatabricksDialect()
        assert dialect.quote_identifier("name`with`ticks") == "`name``with``ticks`"
        assert dialect.quote_identifier("single`tick") == "`single``tick`"

    def test_quote_identifier_multiple_backticks(self):
        """Should handle multiple consecutive backticks."""
        dialect = DatabricksDialect()
        assert dialect.quote_identifier("a``b") == "`a````b`"

    def test_wrap_metric_simple(self):
        """Should wrap simple metric with MEASURE()."""
        dialect = DatabricksDialect()
        assert dialect.wrap_metric("revenue") == "MEASURE(`revenue`)"

    def test_wrap_metric_with_special_chars(self):
        """Should wrap metric with special characters, escaping as needed."""
        dialect = DatabricksDialect()
        assert dialect.wrap_metric("revenue`2024") == "MEASURE(`revenue``2024`)"

    def test_wrap_metric_uppercase(self):
        """Should preserve case in wrapped metrics."""
        dialect = DatabricksDialect()
        assert dialect.wrap_metric("REVENUE") == "MEASURE(`REVENUE`)"


class TestMockDialect:
    """Test MockDialect uses Snowflake syntax for consistency."""

    def test_quote_identifier_uses_double_quotes(self):
        """Should quote identifiers with double quotes like Snowflake."""
        dialect = MockDialect()
        assert dialect.quote_identifier("simple_name") == '"simple_name"'

    def test_quote_identifier_escapes_quotes(self):
        """Should escape internal quotes by doubling them."""
        dialect = MockDialect()
        assert dialect.quote_identifier('name"with"quotes') == '"name""with""quotes"'

    def test_wrap_metric_uses_agg(self):
        """Should wrap metrics with AGG() like Snowflake."""
        dialect = MockDialect()
        assert dialect.wrap_metric("revenue") == 'AGG("revenue")'


class TestSQLBuilderSelectClause:
    """Test SQLBuilder SELECT clause generation."""

    def test_select_single_metric(self):
        """Should select single metric wrapped in AGG()."""
        query = Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "SELECT AGG(" in sql
        assert '"revenue"' in sql

    def test_select_multiple_metrics(self):
        """Should select multiple metrics, each wrapped."""
        query = Query().metrics(Sales.revenue, Sales.cost)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'AGG("revenue")' in sql
        assert 'AGG("cost")' in sql

    def test_select_single_dimension(self):
        """Should select single dimension quoted."""
        query = Query().dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'SELECT "country"' in sql

    def test_select_multiple_dimensions(self):
        """Should select multiple dimensions, each quoted."""
        query = Query().dimensions(Sales.country, Sales.region)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert '"country"' in sql
        assert '"region"' in sql

    def test_select_mixed_metrics_and_dimensions(self):
        """Should select metrics first, then dimensions."""
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        # Metrics come first
        select_clause = sql.split("\n")[0]
        assert 'AGG("revenue")' in select_clause
        assert '"country"' in select_clause
        # AGG should appear before quoted country
        agg_idx = select_clause.index("AGG(")
        country_idx = select_clause.index('"country"')
        assert agg_idx < country_idx


class TestSQLBuilderFromClause:
    """Test SQLBuilder FROM clause generation."""

    def test_from_clause_uses_view_name(self):
        """Should quote and use view name from model."""
        query = Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'FROM "sales_view"' in sql

    def test_from_clause_from_dimensions_model(self):
        """Should extract view name from dimensions if no metrics."""
        query = Query().dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'FROM "sales_view"' in sql

    def test_from_clause_with_snowflake_dialect(self):
        """Should use Snowflake quoting in FROM clause."""
        query = Query().metrics(Sales.revenue)
        builder = SQLBuilder(SnowflakeDialect())
        sql = builder.build_select(query)
        assert 'FROM "sales_view"' in sql

    def test_from_clause_with_databricks_dialect(self):
        """Should use Databricks quoting in FROM clause."""
        query = Query().metrics(Sales.revenue)
        builder = SQLBuilder(DatabricksDialect())
        sql = builder.build_select(query)
        assert "FROM `sales_view`" in sql


class TestSQLBuilderGroupByClause:
    """Test SQLBuilder GROUP BY clause generation."""

    def test_group_by_all_when_dimensions_exist(self):
        """Should include GROUP BY ALL when query has dimensions."""
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "GROUP BY ALL" in sql

    def test_no_group_by_when_only_metrics(self):
        """Should omit GROUP BY when only metrics, no dimensions."""
        query = Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "GROUP BY" not in sql

    def test_no_group_by_when_only_dimensions(self):
        """Should include GROUP BY ALL even with only dimensions."""
        query = Query().dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        # GROUP BY ALL is included when dimensions exist
        assert "GROUP BY ALL" in sql


class TestSQLBuilderOrderByClause:
    """Test SQLBuilder ORDER BY clause generation."""

    def test_order_by_bare_field_ascending(self):
        """Should generate ASC for bare fields."""
        query = Query().dimensions(Sales.country).order_by(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "country" ASC' in sql

    def test_order_by_metric_descending(self):
        """Should generate DESC for field.desc()."""
        query = Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "revenue" DESC' in sql

    def test_order_by_multiple_fields(self):
        """Should generate comma-separated ORDER BY with multiple fields."""
        query = (
            Query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.revenue.desc(), Sales.country.asc())
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert '"revenue" DESC' in sql
        assert '"country" ASC' in sql

    def test_order_by_with_nulls_first(self):
        """Should include NULLS FIRST when specified."""
        query = Query().dimensions(Sales.country).order_by(Sales.country.desc(NullsOrdering.FIRST))
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "country" DESC NULLS FIRST' in sql

    def test_order_by_with_nulls_last(self):
        """Should include NULLS LAST when specified."""
        query = Query().dimensions(Sales.country).order_by(Sales.country.asc(NullsOrdering.LAST))
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "country" ASC NULLS LAST' in sql

    def test_order_by_mixed_nulls_handling(self):
        """Should handle different NULLS handling in same query."""
        query = (
            Query()
            .dimensions(Sales.country, Sales.region)
            .order_by(Sales.country.desc(NullsOrdering.FIRST), Sales.region.asc(NullsOrdering.LAST))
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "NULLS FIRST" in sql
        assert "NULLS LAST" in sql


class TestSQLBuilderLimitClause:
    """Test SQLBuilder LIMIT clause generation."""

    def test_limit_clause_when_set(self):
        """Should include LIMIT when limit is set."""
        query = Query().metrics(Sales.revenue).limit(100)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "LIMIT 100" in sql

    def test_no_limit_clause_when_not_set(self):
        """Should omit LIMIT when limit is None."""
        query = Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "LIMIT" not in sql

    def test_limit_different_values(self):
        """Should use different limit values correctly."""
        for limit_val in [1, 10, 1000, 999999]:
            query = Query().metrics(Sales.revenue).limit(limit_val)
            builder = SQLBuilder(MockDialect())
            sql = builder.build_select(query)
            assert f"LIMIT {limit_val}" in sql


class TestSQLBuilderComplete:
    """Test complete SQL generation with multiple features."""

    def test_full_query_with_metrics_dimensions_limit(self):
        """Should generate complete SQL with all features."""
        query = (
            Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .limit(50)
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)

        # Check all components present
        assert "SELECT" in sql
        assert 'AGG("revenue")' in sql
        assert 'AGG("cost")' in sql
        assert '"country"' in sql
        assert '"region"' in sql
        assert 'FROM "sales_view"' in sql
        assert "GROUP BY ALL" in sql
        assert "LIMIT 50" in sql

    def test_full_query_with_order_by(self):
        """Should generate complete SQL with ORDER BY."""
        query = (
            Query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.revenue.desc())
            .limit(100)
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)

        lines = sql.split("\n")
        # Check order: SELECT, FROM, GROUP BY, ORDER BY, LIMIT
        assert "SELECT" in lines[0]
        assert any("FROM" in line for line in lines)
        assert any("GROUP BY" in line for line in lines)
        assert any("ORDER BY" in line for line in lines)
        assert any("LIMIT" in line for line in lines)

    def test_sql_structure_valid_format(self):
        """Should generate SQL with correct newline separation."""
        query = Query().metrics(Sales.revenue).dimensions(Sales.country).limit(100)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)

        lines = sql.split("\n")
        # Should have multiple lines
        assert len(lines) >= 3
        # Each line should have content
        for line in lines:
            assert line.strip()


class TestQueryToSQL:
    """Test Query.to_sql() integration with SQL generation."""

    def test_to_sql_returns_sql_string(self):
        """Should return SQL string from Query.to_sql()."""
        query = Query().metrics(Sales.revenue)
        sql = query.to_sql()
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_to_sql_uses_mock_dialect(self):
        """Should use MockDialect (Snowflake-like syntax)."""
        query = Query().metrics(Sales.revenue)
        sql = query.to_sql()
        assert 'AGG("revenue")' in sql
        assert 'FROM "sales_view"' in sql

    def test_to_sql_with_dimensions(self):
        """Should include dimensions and GROUP BY ALL."""
        query = Query().metrics(Sales.revenue).dimensions(Sales.country)
        sql = query.to_sql()
        assert 'AGG("revenue")' in sql
        assert '"country"' in sql
        assert "GROUP BY ALL" in sql

    def test_to_sql_with_limit(self):
        """Should include LIMIT clause."""
        query = Query().metrics(Sales.revenue).limit(50)
        sql = query.to_sql()
        assert "LIMIT 50" in sql

    def test_to_sql_with_order_by(self):
        """Should include ORDER BY clause."""
        query = Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        sql = query.to_sql()
        assert 'ORDER BY "revenue" DESC' in sql

    def test_to_sql_validates_empty_query(self):
        """Should raise ValueError for empty query."""
        query = Query()
        with pytest.raises(ValueError):
            query.to_sql()

    def test_to_sql_complex_query(self):
        """Should handle complex query with many features."""
        query = (
            Query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .order_by(Sales.revenue.desc(NullsOrdering.FIRST))
            .limit(100)
        )
        sql = query.to_sql()
        assert 'AGG("revenue")' in sql
        assert 'AGG("cost")' in sql
        assert '"country"' in sql
        assert '"region"' in sql
        assert "GROUP BY ALL" in sql
        assert 'ORDER BY "revenue" DESC NULLS FIRST' in sql
        assert "LIMIT 100" in sql


class TestDialectEscaping:
    """Test edge cases for identifier escaping."""

    def test_snowflake_empty_identifier(self):
        """Should handle empty identifier (edge case)."""
        dialect = SnowflakeDialect()
        assert dialect.quote_identifier("") == '""'

    def test_databricks_empty_identifier(self):
        """Should handle empty identifier (edge case)."""
        dialect = DatabricksDialect()
        assert dialect.quote_identifier("") == "``"

    def test_snowflake_only_quotes(self):
        """Should handle identifier that is only quotes."""
        dialect = SnowflakeDialect()
        # Three quotes -> escaped to six quotes inside, wrapped = 8 total
        assert dialect.quote_identifier('"""') == '""""""""'

    def test_databricks_only_backticks(self):
        """Should handle identifier that is only backticks."""
        dialect = DatabricksDialect()
        # Three backticks -> escaped to six backticks inside, wrapped = 8 total
        assert dialect.quote_identifier("```") == "````````"

    def test_snowflake_mixed_quotes_and_text(self):
        """Should handle mixed quotes and text."""
        dialect = SnowflakeDialect()
        result = dialect.quote_identifier('a"b"c')
        assert result == '"a""b""c"'
        # Verify unescaping would work: remove outer quotes, replace "" with "
        inner = result[1:-1]  # Remove outer quotes
        assert inner.replace('""', '"') == 'a"b"c'

    def test_databricks_mixed_backticks_and_text(self):
        """Should handle mixed backticks and text."""
        dialect = DatabricksDialect()
        result = dialect.quote_identifier("a`b`c")
        assert result == "`a``b``c`"
        # Verify unescaping would work
        inner = result[1:-1]  # Remove outer quotes
        assert inner.replace("``", "`") == "a`b`c"
