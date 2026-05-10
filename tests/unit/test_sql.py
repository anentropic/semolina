"""
Tests for SQL generation with Dialect and SQLBuilder classes.

Tests cover:
- SQL-01: Query.to_sql() generates valid SQL
- SQL-02: SnowflakeDialect uses double quotes and AGG() wrapping
- SQL-03: DatabricksDialect uses backticks and MEASURE() wrapping
- SQL-04: GROUP BY ALL for automatic dimension derivation
- SQL-05: Proper identifier quoting and escaping
- SQL-06: Dialect.placeholder property (%s vs ?)
- SQL-07: WHERE clause compiler (_compile_predicate)
- SQL-08: build_select_with_params parameterized output
- SQL-09: render_inline for display/debugging
"""

from dataclasses import replace

import pytest
from models import Sales

from semolina.engines.sql import (
    DatabricksDialect,
    DuckDBDialect,
    DuckDBSQLBuilder,
    MockDialect,
    SnowflakeDialect,
    SQLBuilder,
)
from semolina.fields import NullsOrdering
from semolina.filters import (
    And,
    Between,
    EndsWith,
    Exact,
    Gt,
    Gte,
    IEndsWith,
    IExact,
    ILike,
    In,
    IsNull,
    IStartsWith,
    Like,
    Lookup,
    Lt,
    Lte,
    NotEqual,
    Or,
    StartsWith,
)
from semolina.query import _Query


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
        query = _Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "SELECT AGG(" in sql
        assert '"revenue"' in sql

    def test_select_multiple_metrics(self):
        """Should select multiple metrics, each wrapped."""
        query = _Query().metrics(Sales.revenue, Sales.cost)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'AGG("revenue")' in sql
        assert 'AGG("cost")' in sql

    def test_select_single_dimension(self):
        """Should select single dimension quoted."""
        query = _Query().dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'SELECT "country"' in sql

    def test_select_multiple_dimensions(self):
        """Should select multiple dimensions, each quoted."""
        query = _Query().dimensions(Sales.country, Sales.region)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert '"country"' in sql
        assert '"region"' in sql

    def test_select_mixed_metrics_and_dimensions(self):
        """Should select metrics first, then dimensions."""
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
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
        query = _Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'FROM "sales_view"' in sql

    def test_from_clause_from_dimensions_model(self):
        """Should extract view name from dimensions if no metrics."""
        query = _Query().dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'FROM "sales_view"' in sql

    def test_from_clause_with_snowflake_dialect(self):
        """Should use Snowflake quoting in FROM clause."""
        query = _Query().metrics(Sales.revenue)
        builder = SQLBuilder(SnowflakeDialect())
        sql = builder.build_select(query)
        assert 'FROM "sales_view"' in sql

    def test_from_clause_with_databricks_dialect(self):
        """Should use Databricks quoting in FROM clause."""
        query = _Query().metrics(Sales.revenue)
        builder = SQLBuilder(DatabricksDialect())
        sql = builder.build_select(query)
        assert "FROM `sales_view`" in sql


class TestSQLBuilderGroupByClause:
    """Test SQLBuilder GROUP BY clause generation."""

    def test_group_by_all_when_dimensions_exist(self):
        """Should include GROUP BY ALL when query has dimensions."""
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "GROUP BY ALL" in sql

    def test_no_group_by_when_only_metrics(self):
        """Should omit GROUP BY when only metrics, no dimensions."""
        query = _Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "GROUP BY" not in sql

    def test_no_group_by_when_only_dimensions(self):
        """Should include GROUP BY ALL even with only dimensions."""
        query = _Query().dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        # GROUP BY ALL is included when dimensions exist
        assert "GROUP BY ALL" in sql


class TestSQLBuilderOrderByClause:
    """Test SQLBuilder ORDER BY clause generation."""

    def test_order_by_bare_field_ascending(self):
        """Should generate ASC for bare fields."""
        query = _Query().dimensions(Sales.country).order_by(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "country" ASC' in sql

    def test_order_by_metric_descending(self):
        """Should generate DESC for field.desc()."""
        query = _Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY AGG("revenue") DESC' in sql

    def test_order_by_multiple_fields(self):
        """Should generate comma-separated ORDER BY with multiple fields."""
        query = (
            _Query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.revenue.desc(), Sales.country.asc())
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'AGG("revenue") DESC' in sql
        assert '"country" ASC' in sql

    def test_order_by_with_nulls_first(self):
        """Should include NULLS FIRST when specified."""
        query = _Query().dimensions(Sales.country).order_by(Sales.country.desc(NullsOrdering.FIRST))
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "country" DESC NULLS FIRST' in sql

    def test_order_by_with_nulls_last(self):
        """Should include NULLS LAST when specified."""
        query = _Query().dimensions(Sales.country).order_by(Sales.country.asc(NullsOrdering.LAST))
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert 'ORDER BY "country" ASC NULLS LAST' in sql

    def test_order_by_mixed_nulls_handling(self):
        """Should handle different NULLS handling in same query."""
        query = (
            _Query()
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
        query = _Query().metrics(Sales.revenue).limit(100)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "LIMIT 100" in sql

    def test_no_limit_clause_when_not_set(self):
        """Should omit LIMIT when limit is None."""
        query = _Query().metrics(Sales.revenue)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "LIMIT" not in sql

    def test_limit_different_values(self):
        """Should use different limit values correctly."""
        for limit_val in [1, 10, 1000, 999999]:
            query = _Query().metrics(Sales.revenue).limit(limit_val)
            builder = SQLBuilder(MockDialect())
            sql = builder.build_select(query)
            assert f"LIMIT {limit_val}" in sql


class TestSQLBuilderComplete:
    """Test complete SQL generation with multiple features."""

    def test_full_query_with_metrics_dimensions_limit(self):
        """Should generate complete SQL with all features."""
        query = (
            _Query()
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
            _Query()
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
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country).limit(100)
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
        query = _Query().metrics(Sales.revenue)
        sql = query.to_sql()
        assert isinstance(sql, str)
        assert "SELECT" in sql

    def test_to_sql_uses_mock_dialect(self):
        """Should use MockDialect (Snowflake-like syntax)."""
        query = _Query().metrics(Sales.revenue)
        sql = query.to_sql()
        assert 'AGG("revenue")' in sql
        assert 'FROM "sales_view"' in sql

    def test_to_sql_with_dimensions(self):
        """Should include dimensions and GROUP BY ALL."""
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        sql = query.to_sql()
        assert 'AGG("revenue")' in sql
        assert '"country"' in sql
        assert "GROUP BY ALL" in sql

    def test_to_sql_with_limit(self):
        """Should include LIMIT clause."""
        query = _Query().metrics(Sales.revenue).limit(50)
        sql = query.to_sql()
        assert "LIMIT 50" in sql

    def test_to_sql_with_order_by(self):
        """Should include ORDER BY clause."""
        query = _Query().metrics(Sales.revenue).order_by(Sales.revenue.desc())
        sql = query.to_sql()
        assert 'ORDER BY AGG("revenue") DESC' in sql

    def test_to_sql_validates_empty_query(self):
        """Should raise ValueError for empty query."""
        query = _Query()
        with pytest.raises(ValueError):
            query.to_sql()

    def test_to_sql_complex_query(self):
        """Should handle complex query with many features."""
        query = (
            _Query()
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
        assert 'ORDER BY AGG("revenue") DESC NULLS FIRST' in sql
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


# ---------------------------------------------------------------------------
# Phase 13.1 Plan 03: Dialect.placeholder, WHERE compiler, parameterization
# ---------------------------------------------------------------------------


class TestDialectPlaceholder:
    """Test Dialect.placeholder property returns backend-specific placeholder."""

    def test_snowflake_placeholder(self):
        """SnowflakeDialect.placeholder should return %s."""
        assert SnowflakeDialect().placeholder == "%s"

    def test_databricks_placeholder(self):
        """DatabricksDialect.placeholder should return ?."""
        assert DatabricksDialect().placeholder == "?"

    def test_mock_placeholder(self):
        """MockDialect.placeholder should return %s (Snowflake-compatible)."""
        assert MockDialect().placeholder == "%s"


class TestWhereClauseCompiler:
    """Test _compile_predicate pattern-matching for all node types."""

    def setup_method(self):
        """Create a SQLBuilder with MockDialect for each test."""
        self.builder = SQLBuilder(MockDialect())

    # -- Leaf lookups (15 types) -----------------------------------------------

    def test_compile_exact(self):
        """Exact(f, v) -> '{quote(f)} = {ph}', [v]."""
        sql, params = self.builder._compile_predicate(Exact("country", "US"))
        assert sql == '"country" = %s'
        assert params == ["US"]

    def test_compile_not_equal(self):
        """NotEqual(f, v) -> '{quote(f)} != {ph}', [v]."""
        sql, params = self.builder._compile_predicate(NotEqual("country", "US"))
        assert sql == '"country" != %s'
        assert params == ["US"]

    def test_compile_gt(self):
        """Gt(f, v) -> '{quote(f)} > {ph}', [v]."""
        sql, params = self.builder._compile_predicate(Gt("revenue", 1000))
        assert sql == '"revenue" > %s'
        assert params == [1000]

    def test_compile_gte(self):
        """Gte(f, v) -> '{quote(f)} >= {ph}', [v]."""
        sql, params = self.builder._compile_predicate(Gte("revenue", 500))
        assert sql == '"revenue" >= %s'
        assert params == [500]

    def test_compile_lt(self):
        """Lt(f, v) -> '{quote(f)} < {ph}', [v]."""
        sql, params = self.builder._compile_predicate(Lt("revenue", 100))
        assert sql == '"revenue" < %s'
        assert params == [100]

    def test_compile_lte(self):
        """Lte(f, v) -> '{quote(f)} <= {ph}', [v]."""
        sql, params = self.builder._compile_predicate(Lte("revenue", 50))
        assert sql == '"revenue" <= %s'
        assert params == [50]

    def test_compile_in_with_values(self):
        """In(f, [a,b,c]) -> '{quote(f)} IN ({ph}, {ph}, {ph})', [a, b, c]."""
        sql, params = self.builder._compile_predicate(In("country", ["US", "CA", "UK"]))
        assert sql == '"country" IN (%s, %s, %s)'
        assert params == ["US", "CA", "UK"]

    def test_compile_in_single_value(self):
        """In(f, [a]) -> '{quote(f)} IN ({ph})', [a]."""
        sql, params = self.builder._compile_predicate(In("country", ["US"]))
        assert sql == '"country" IN (%s)'
        assert params == ["US"]

    def test_compile_in_empty(self):
        """In(f, []) -> '1 = 0', [] (always false, Django precedent)."""
        sql, params = self.builder._compile_predicate(In("country", []))
        assert sql == "1 = 0"
        assert params == []

    def test_compile_between(self):
        """Between(f, (lo, hi)) -> '{quote(f)} BETWEEN {ph} AND {ph}', [lo, hi]."""
        sql, params = self.builder._compile_predicate(Between("revenue", (100, 500)))
        assert sql == '"revenue" BETWEEN %s AND %s'
        assert params == [100, 500]

    def test_compile_is_null_true(self):
        """IsNull(f, True) -> '{quote(f)} IS NULL', []."""
        sql, params = self.builder._compile_predicate(IsNull("country", True))
        assert sql == '"country" IS NULL'
        assert params == []

    def test_compile_is_null_false(self):
        """IsNull(f, False) -> '{quote(f)} IS NOT NULL', []."""
        sql, params = self.builder._compile_predicate(IsNull("country", False))
        assert sql == '"country" IS NOT NULL'
        assert params == []

    def test_compile_like(self):
        """Like(f, v) -> '{quote(f)} LIKE {ph}', [v]."""
        sql, params = self.builder._compile_predicate(Like("name", "%test%"))
        assert sql == '"name" LIKE %s'
        assert params == ["%test%"]

    def test_compile_ilike(self):
        """ILike(f, v) -> '{quote(f)} ILIKE {ph}', [v]."""
        sql, params = self.builder._compile_predicate(ILike("name", "%test%"))
        assert sql == '"name" ILIKE %s'
        assert params == ["%test%"]

    def test_compile_starts_with(self):
        """StartsWith(f, v) -> '{quote(f)} LIKE {ph}', [v + '%']."""
        sql, params = self.builder._compile_predicate(StartsWith("name", "test"))
        assert sql == '"name" LIKE %s'
        assert params == ["test%"]

    def test_compile_istarts_with(self):
        """IStartsWith(f, v) -> '{quote(f)} ILIKE {ph}', [v + '%']."""
        sql, params = self.builder._compile_predicate(IStartsWith("name", "test"))
        assert sql == '"name" ILIKE %s'
        assert params == ["test%"]

    def test_compile_ends_with(self):
        """EndsWith(f, v) -> '{quote(f)} LIKE {ph}', ['%' + v]."""
        sql, params = self.builder._compile_predicate(EndsWith("name", "test"))
        assert sql == '"name" LIKE %s'
        assert params == ["%test"]

    def test_compile_iends_with(self):
        """IEndsWith(f, v) -> '{quote(f)} ILIKE {ph}', ['%' + v]."""
        sql, params = self.builder._compile_predicate(IEndsWith("name", "test"))
        assert sql == '"name" ILIKE %s'
        assert params == ["%test"]

    def test_compile_iexact(self):
        """IExact(f, v) -> '{quote(f)} ILIKE {ph}', [v] (no wildcards)."""
        sql, params = self.builder._compile_predicate(IExact("name", "Test"))
        assert sql == '"name" ILIKE %s'
        assert params == ["Test"]

    # -- Composite nodes -------------------------------------------------------

    def test_compile_and(self):
        """And(l, r) -> '({l_sql} AND {r_sql})', l_params + r_params."""
        pred = Exact("country", "US") & Gt("revenue", 1000)
        sql, params = self.builder._compile_predicate(pred)
        assert sql == '("country" = %s AND "revenue" > %s)'
        assert params == ["US", 1000]

    def test_compile_or(self):
        """Or(l, r) -> '({l_sql} OR {r_sql})', l_params + r_params."""
        pred = Exact("country", "US") | Exact("country", "CA")
        sql, params = self.builder._compile_predicate(pred)
        assert sql == '("country" = %s OR "country" = %s)'
        assert params == ["US", "CA"]

    def test_compile_not(self):
        """Not(i) -> 'NOT ({i_sql})', i_params."""
        pred = ~Exact("country", "US")
        sql, params = self.builder._compile_predicate(pred)
        assert sql == 'NOT ("country" = %s)'
        assert params == ["US"]

    def test_compile_nested_and_or_not(self):
        """(a & b) | ~c compiles correctly."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        c = Exact("region", "West")
        pred = (a & b) | ~c
        sql, params = self.builder._compile_predicate(pred)
        assert sql == '(("country" = %s AND "revenue" > %s) OR NOT ("region" = %s))'
        assert params == ["US", 1000, "West"]

    def test_compile_double_not(self):
        """~~predicate -> NOT (NOT ({sql}))."""
        pred = ~~Exact("country", "US")
        sql, params = self.builder._compile_predicate(pred)
        assert sql == 'NOT (NOT ("country" = %s))'
        assert params == ["US"]

    # -- Param accumulation ----------------------------------------------------

    def test_params_accumulated_correctly(self):
        """Composite predicates accumulate params from all children in order."""
        pred = And(
            left=Or(
                left=Exact("a", 1),
                right=Exact("b", 2),
            ),
            right=Gt("c", 3),
        )
        _sql, params = self.builder._compile_predicate(pred)
        assert params == [1, 2, 3]

    # -- Dialect-specific placeholders -----------------------------------------

    def test_databricks_placeholder_in_compilation(self):
        """Databricks uses ? placeholder in compiled SQL."""
        builder = SQLBuilder(DatabricksDialect())
        sql, params = builder._compile_predicate(Exact("country", "US"))
        assert sql == "`country` = ?"
        assert params == ["US"]

    def test_databricks_in_placeholder(self):
        """Databricks uses ? placeholder in IN clause."""
        builder = SQLBuilder(DatabricksDialect())
        sql, params = builder._compile_predicate(In("country", ["US", "CA"]))
        assert sql == "`country` IN (?, ?)"
        assert params == ["US", "CA"]

    # -- Error cases -----------------------------------------------------------

    def test_unknown_lookup_raises_not_implemented(self):
        """Unknown Lookup subclass raises NotImplementedError."""

        class CustomLookup(Lookup[str]):
            """A custom lookup that the compiler doesn't know about."""

        pred = CustomLookup("field", "value")
        with pytest.raises(NotImplementedError):
            self.builder._compile_predicate(pred)

    def test_non_predicate_raises_type_error(self):
        """Non-Predicate input raises TypeError."""
        with pytest.raises(TypeError):
            self.builder._compile_predicate("not a predicate")  # type: ignore[arg-type]


class TestBuildSelectWithParams:
    """Test build_select_with_params returns (sql_template, params)."""

    def test_query_with_filters(self):
        """Query with filters produces (sql_template, params)."""
        query = replace(
            _Query().metrics(Sales.revenue).dimensions(Sales.country),
            _filters=Exact("country", "US"),
        )
        builder = SQLBuilder(MockDialect())
        sql, params = builder.build_select_with_params(query)
        assert "WHERE" in sql
        assert '"country" = %s' in sql
        assert params == ["US"]
        # Literal value should NOT be in SQL template
        assert "'US'" not in sql

    def test_query_without_filters(self):
        """Query without filters produces (sql, [])."""
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql, params = builder.build_select_with_params(query)
        assert "WHERE" not in sql
        assert params == []

    def test_placeholder_in_template_not_literal(self):
        """Params placeholder appears in SQL template, not literal values."""
        query = replace(
            _Query().metrics(Sales.revenue).dimensions(Sales.country),
            _filters=Gt("revenue", 1000),
        )
        builder = SQLBuilder(MockDialect())
        sql, params = builder.build_select_with_params(query)
        assert "%s" in sql
        assert "1000" not in sql
        assert params == [1000]

    def test_complex_filter_with_params(self):
        """Complex filter accumulates all params in order."""
        pred = Exact("country", "US") & Gt("revenue", 500)
        query = replace(
            _Query().metrics(Sales.revenue).dimensions(Sales.country),
            _filters=pred,
        )
        builder = SQLBuilder(MockDialect())
        _sql, params = builder.build_select_with_params(query)
        assert params == ["US", 500]


class TestRenderInline:
    """Test render_inline substitutes params with repr()."""

    def test_render_inline_single_param(self):
        """render_inline substitutes single param with repr()."""
        builder = SQLBuilder(MockDialect())
        result = builder.render_inline('"country" = %s', ["US"])
        assert result == "\"country\" = 'US'"

    def test_render_inline_multiple_params(self):
        """render_inline substitutes multiple params in order."""
        builder = SQLBuilder(MockDialect())
        result = builder.render_inline(
            '"country" = %s AND "revenue" > %s',
            ["US", 1000],
        )
        assert result == '"country" = \'US\' AND "revenue" > 1000'

    def test_render_inline_no_params(self):
        """render_inline with no params returns unchanged SQL."""
        builder = SQLBuilder(MockDialect())
        result = builder.render_inline("SELECT 1", [])
        assert result == "SELECT 1"

    def test_render_inline_databricks_placeholder(self):
        """render_inline works with ? placeholder for Databricks."""
        builder = SQLBuilder(DatabricksDialect())
        result = builder.render_inline("`country` = ?", ["US"])
        assert result == "`country` = 'US'"


class TestBuildSelectBackwardCompat:
    """Test build_select() returns inline-rendered SQL (backward compatible)."""

    def test_build_select_with_filter_renders_inline(self):
        """build_select() with filters renders params inline for display."""
        query = replace(
            _Query().metrics(Sales.revenue).dimensions(Sales.country),
            _filters=Exact("country", "US"),
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert isinstance(sql, str)
        # Should contain the inline-rendered value, not placeholder
        assert "'US'" in sql
        assert "WHERE" in sql
        # Should NOT contain raw %s placeholder
        assert "%s" not in sql

    def test_build_select_no_filter_unchanged(self):
        """build_select() without filters works as before."""
        query = _Query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert isinstance(sql, str)
        assert "WHERE" not in sql
        assert 'AGG("revenue")' in sql

    def test_no_where_1_equals_1_placeholder(self):
        """WHERE 1=1 placeholder is gone in favor of real compiler."""
        query = replace(
            _Query().metrics(Sales.revenue).dimensions(Sales.country),
            _filters=Exact("country", "US"),
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        assert "WHERE 1=1" not in sql


# ---------------------------------------------------------------------------
# Phase 20.1 Plan 02: normalize_identifier and _resolve_col_name
# ---------------------------------------------------------------------------


class TestNormalizeIdentifier:
    """Test normalize_identifier on each dialect."""

    def test_snowflake_normalizes_to_uppercase(self):
        """SnowflakeDialect.normalize_identifier returns uppercase."""
        dialect = SnowflakeDialect()
        assert dialect.normalize_identifier("order_id") == "ORDER_ID"
        assert dialect.normalize_identifier("revenue") == "REVENUE"
        assert dialect.normalize_identifier("my_field_name") == "MY_FIELD_NAME"

    def test_databricks_normalizes_to_lowercase(self):
        """DatabricksDialect.normalize_identifier returns lowercase."""
        dialect = DatabricksDialect()
        assert dialect.normalize_identifier("ORDER_ID") == "order_id"
        assert dialect.normalize_identifier("Revenue") == "revenue"
        assert dialect.normalize_identifier("MY_FIELD") == "my_field"

    def test_mock_is_identity(self):
        """MockDialect.normalize_identifier returns name unchanged."""
        dialect = MockDialect()
        assert dialect.normalize_identifier("order_id") == "order_id"
        assert dialect.normalize_identifier("ORDER_ID") == "ORDER_ID"
        assert dialect.normalize_identifier("Revenue") == "Revenue"


class TestResolveColName:
    """Test _resolve_col_name helper on SQLBuilder."""

    def test_field_with_source_uses_source_verbatim(self):
        """Field with source= set uses that value verbatim, no normalization."""
        from semolina import Metric

        # Simulate a field with explicit source
        field = Metric[int](source="order_id")
        field.__set_name__(None, "order_id")  # type: ignore[arg-type]

        builder = SQLBuilder(SnowflakeDialect())
        assert builder._resolve_col_name(field) == "order_id"

    def test_field_without_source_uses_normalize_snowflake(self):
        """Field without source uses dialect.normalize_identifier (Snowflake → UPPER)."""
        from semolina import Metric

        field = Metric[int]()
        field.__set_name__(None, "order_id")  # type: ignore[arg-type]

        builder = SQLBuilder(SnowflakeDialect())
        assert builder._resolve_col_name(field) == "ORDER_ID"

    def test_field_without_source_uses_normalize_databricks(self):
        """Field without source uses dialect.normalize_identifier (Databricks → lower)."""
        from semolina import Metric

        field = Metric[int]()
        field.__set_name__(None, "ORDER_ID")  # type: ignore[arg-type]

        builder = SQLBuilder(DatabricksDialect())
        assert builder._resolve_col_name(field) == "order_id"

    def test_field_without_source_uses_normalize_mock(self):
        """Field without source uses dialect.normalize_identifier (Mock → identity)."""
        from semolina import Metric

        field = Metric[int]()
        field.__set_name__(None, "revenue")  # type: ignore[arg-type]

        builder = SQLBuilder(MockDialect())
        assert builder._resolve_col_name(field) == "revenue"


class TestWhereClauseNormalization:
    """Test WHERE clause field_name normalization through dialect."""

    def test_snowflake_where_normalizes_field_name_to_uppercase(self):
        """Snowflake WHERE clause normalizes Python field_name to UPPERCASE."""
        builder = SQLBuilder(SnowflakeDialect())
        sql, params = builder._compile_predicate(Exact("order_id", "ORD-001"))
        assert sql == '"ORDER_ID" = %s'
        assert params == ["ORD-001"]

    def test_databricks_where_normalizes_field_name_to_lowercase(self):
        """Databricks WHERE clause normalizes Python field_name to lowercase."""
        builder = SQLBuilder(DatabricksDialect())
        sql, params = builder._compile_predicate(Exact("ORDER_ID", "ORD-001"))
        assert sql == "`order_id` = ?"
        assert params == ["ORD-001"]

    def test_mock_where_field_name_unchanged(self):
        """Mock WHERE clause leaves field_name unchanged (identity)."""
        builder = SQLBuilder(MockDialect())
        sql, params = builder._compile_predicate(Exact("order_id", "ORD-001"))
        assert sql == '"order_id" = %s'
        assert params == ["ORD-001"]


class TestWhereClauseSourceOverride:
    """Regression tests: source= override propagates through WHERE clause compiler."""

    def test_metric_with_source_uses_source_in_where(self):
        """Metric(source='revenue_usd') WHERE emits 'revenue_usd', not normalized Python name."""
        from semolina import Metric, SemanticView
        from semolina.query import _Query

        class MyView(SemanticView, view="my_view"):
            revenue_usd_field = Metric[int](source="revenue_usd")

        query = _Query().metrics(MyView.revenue_usd_field).where(MyView.revenue_usd_field > 100)
        sql = query.to_sql()
        # source= value used verbatim in WHERE
        assert '"revenue_usd"' in sql
        # Python attribute name NOT used in WHERE
        assert '"revenue_usd_field"' not in sql
        # Snowflake-normalized Python name NOT used in WHERE
        assert '"REVENUE_USD_FIELD"' not in sql

    def test_select_and_where_column_names_match_when_source_set(self):
        """SELECT and WHERE use identical column names for fields with source=."""
        from semolina import Metric, SemanticView
        from semolina.query import _Query

        class MyView2(SemanticView, view="my_view2"):
            revenue_usd_field = Metric[int](source="revenue_usd")

        query = _Query().metrics(MyView2.revenue_usd_field).where(MyView2.revenue_usd_field > 100)
        sql = query.to_sql()
        # Both SELECT and WHERE must reference the same column name
        # SELECT will have AGG("revenue_usd") and WHERE must have "revenue_usd"
        assert '"revenue_usd"' in sql
        # The normalized Python name should not appear anywhere
        assert '"revenue_usd_field"' not in sql
        assert '"REVENUE_USD_FIELD"' not in sql

    def test_field_without_source_where_still_normalized(self):
        """Field without source= still gets dialect normalization in WHERE."""
        builder = SQLBuilder(SnowflakeDialect())
        # No source= set, so source defaults to None
        pred = Exact("revenue", "US")
        sql, params = builder._compile_predicate(pred)
        # Snowflake normalization: revenue -> REVENUE
        assert sql == '"REVENUE" = %s'
        assert params == ["US"]


# ---------------------------------------------------------------------------
# DuckDB Dialect tests
# ---------------------------------------------------------------------------


class TestDuckDBDialect:
    """Test DuckDBDialect identifier quoting, metric wrapping, and factory."""

    def test_placeholder(self):
        """DuckDBDialect uses ? placeholder (qmark paramstyle)."""
        assert DuckDBDialect().placeholder == "?"

    def test_quote_identifier_simple(self):
        """Should quote simple identifiers with double quotes."""
        assert DuckDBDialect().quote_identifier("col") == '"col"'

    def test_quote_identifier_escapes(self):
        """Should escape internal double quotes by doubling them."""
        assert DuckDBDialect().quote_identifier('a"b') == '"a""b"'

    def test_wrap_metric_returns_plain_quoted(self):
        """wrap_metric returns plain quoted identifier (no AGG/MEASURE)."""
        assert DuckDBDialect().wrap_metric("revenue") == '"revenue"'

    def test_normalize_identifier_lowercase(self):
        """DuckDB normalizes identifiers to lowercase."""
        assert DuckDBDialect().normalize_identifier("REVENUE") == "revenue"

    def test_create_builder_returns_duckdb_builder(self):
        """create_builder() returns DuckDBSQLBuilder instance."""
        assert isinstance(DuckDBDialect().create_builder(), DuckDBSQLBuilder)


# ---------------------------------------------------------------------------
# create_builder() factory method tests
# ---------------------------------------------------------------------------


class TestCreateBuilderFactory:
    """Test that create_builder() returns the correct builder for each dialect."""

    def test_snowflake_creates_base_builder(self):
        """SnowflakeDialect.create_builder() returns base SQLBuilder."""
        builder = SnowflakeDialect().create_builder()
        assert isinstance(builder, SQLBuilder)
        assert not isinstance(builder, DuckDBSQLBuilder)

    def test_databricks_creates_base_builder(self):
        """DatabricksDialect.create_builder() returns base SQLBuilder."""
        builder = DatabricksDialect().create_builder()
        assert isinstance(builder, SQLBuilder)
        assert not isinstance(builder, DuckDBSQLBuilder)

    def test_mock_creates_base_builder(self):
        """MockDialect.create_builder() returns base SQLBuilder."""
        builder = MockDialect().create_builder()
        assert isinstance(builder, SQLBuilder)
        assert not isinstance(builder, DuckDBSQLBuilder)


# ---------------------------------------------------------------------------
# DuckDB SQL Builder tests
# ---------------------------------------------------------------------------


class TestDuckDBSQLBuilder:
    """Test DuckDBSQLBuilder generates correct semantic_view() SQL."""

    def test_grouped_query_sql(self):
        """Dimensions + metrics produces semantic_view() with both args."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            "SELECT *\n"
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue'])"
        )
        assert params == []

    def test_facts_only_query(self):
        """Facts only produces semantic_view() with facts arg."""
        query = Sales.query().dimensions(Sales.unit_price)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == "SELECT *\nFROM semantic_view('sales_view', facts := ['unit_price'])"
        assert params == []

    def test_facts_and_dimensions_query(self):
        """Dimensions + facts produces semantic_view() with both args."""
        query = Sales.query().dimensions(Sales.country, Sales.unit_price)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            "SELECT *\n"
            "FROM semantic_view('sales_view', "
            "dimensions := ['country'], facts := ['unit_price'])"
        )
        assert params == []

    def test_facts_and_metrics_raises(self):
        """ValueError when both facts and metrics are present."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.unit_price)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        with pytest.raises(ValueError, match="combining facts and metrics"):
            builder.build_select_with_params(query)

    def test_where_clause(self):
        """WHERE appears as outer SQL with ? placeholder."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert 'WHERE "country" = ?' in sql
        assert params == ["US"]

    def test_where_dimension_not_selected_is_requested_from_semantic_view(self):
        """DuckDB must request filtered dimensions even when not projected."""
        query = Sales.query().metrics(Sales.revenue).where(Sales.country == "US")
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            "SELECT *\n"
            "FROM semantic_view('sales_view', dimensions := ['country'], metrics := ['revenue'])\n"
            'WHERE "country" = ?'
        )
        assert params == ["US"]

    def test_order_by_metric_no_agg_wrap(self):
        """ORDER BY uses plain quoted identifier for metrics (no AGG/MEASURE)."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.revenue.desc())
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert 'ORDER BY "revenue" DESC' in sql
        assert "AGG(" not in sql
        assert "MEASURE(" not in sql

    def test_order_by_dimension(self):
        """ORDER BY dimension uses plain quoted identifier."""
        query = (
            Sales.query().metrics(Sales.revenue).dimensions(Sales.country).order_by(Sales.country)
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert 'ORDER BY "country" ASC' in sql

    def test_order_by_dimension_not_selected_is_requested_from_semantic_view(self):
        """DuckDB must request sort dimensions even when not projected."""
        query = Sales.query().metrics(Sales.revenue).order_by(Sales.country)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            "SELECT *\n"
            "FROM semantic_view('sales_view', dimensions := ['country'], metrics := ['revenue'])\n"
            'ORDER BY "country" ASC'
        )
        assert params == []

    def test_limit(self):
        """LIMIT N as outer SQL."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).limit(10)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert "LIMIT 10" in sql

    def test_full_query_with_where_order_limit(self):
        """Full query with WHERE + ORDER BY + LIMIT produces correct multi-line SQL."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
            .order_by(Sales.revenue.desc())
            .limit(10)
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        expected = (
            "SELECT *\n"
            "FROM semantic_view('sales_view', "
            "dimensions := ['country'], metrics := ['revenue'])\n"
            'WHERE "country" = ?\n'
            'ORDER BY "revenue" DESC\n'
            "LIMIT 10"
        )
        assert sql == expected
        assert params == ["US"]

    def test_multiple_dimensions_and_metrics(self):
        """Multiple dimensions and metrics are listed correctly."""
        query = (
            Sales.query().metrics(Sales.revenue, Sales.cost).dimensions(Sales.country, Sales.region)
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert "dimensions := ['country', 'region']" in sql
        assert "metrics := ['revenue', 'cost']" in sql

    def test_build_select_renders_inline(self):
        """build_select() renders params inline (no ? placeholders)."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql = builder.build_select(query)
        assert "'US'" in sql
        assert "?" not in sql

    def test_dimensions_only_query(self):
        """Dimensions only (no metrics, no facts) produces correct SQL."""
        query = Sales.query().dimensions(Sales.country)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == "SELECT *\nFROM semantic_view('sales_view', dimensions := ['country'])"
        assert params == []
