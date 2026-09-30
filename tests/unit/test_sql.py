"""
Tests for SQL generation with Dialect and SQLBuilder classes, dialect by dialect.

``test_query.py`` pins the builder's clauses as exact Snowflake statements. This module pins
what differs by dialect — quoting, metric wrapping, name folding, bound versus inlined
parameters, literal rendering — and the WHERE compiler, whose conditions are read off a real
query built through ``.where()`` rather than off the private compiler method.

Tests cover:
- Query.to_sql() generates valid SQL
- SnowflakeDialect uses double quotes and AGG() wrapping
- DatabricksDialect uses backticks and MEASURE() wrapping
- GROUP BY ALL for automatic dimension derivation
- Proper identifier quoting and escaping
- Dialect.placeholder property (qmark "?" across ADBC backends)
- WHERE clause compilation, through ``.where()`` and the dialect's builder
- build_select_with_params parameterized output
- render_inline for display/debugging
"""

import datetime
import re
from collections.abc import Callable, Iterable
from decimal import Decimal

import pytest
from models import Sales

from semolina.dialect import resolve_dialect
from semolina.engines.sql import (
    DatabricksDialect,
    DuckDBDialect,
    DuckDBSQLBuilder,
    SnowflakeDialect,
    SQLBuilder,
)
from semolina.fields import Dimension, Fact, Metric, NullsOrdering
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
from semolina.models import SemanticView


def where_clause(predicate: object, dialect: str = "snowflake") -> tuple[str, list[object]]:
    """
    Compile one predicate the way execution does, and return its WHERE condition and params.

    The predicate is attached to a real query with ``.where()`` and built by the dialect's own
    builder, exactly as ``Engine.execute`` builds it, so the condition asserted is the one a
    warehouse would receive.

    Args:
        predicate: What to pass to ``.where()``.
        dialect: A dialect name.

    Returns:
        The WHERE condition without the ``WHERE`` keyword, and the bound parameters.
    """
    query = Sales.query().metrics(Sales.revenue).where(predicate)  # pyright: ignore[reportArgumentType]
    sql, params = resolve_dialect(dialect).create_builder().build_select_with_params(query)
    where = [line for line in sql.split("\n") if line.startswith("WHERE ")]
    assert len(where) == 1, sql
    return where[0].removeprefix("WHERE "), params


DUCKDB_SALES = (
    'SELECT "revenue" AS "revenue", "country" AS "country"\n'
    "FROM semantic_view('sales_view', dimensions := ['country'], metrics := ['revenue'])"
)
"""The DuckDB statement head for revenue by country; the clauses under test follow it."""


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

    def test_metric_result_column_name_matches_wrap_metric(self):
        """For an already-upper-case metric name the label equals the expression sent."""
        dialect = SnowflakeDialect()
        assert dialect.metric_result_column_name("REVENUE") == 'AGG("REVENUE")'
        assert dialect.metric_result_column_name("REVENUE") == dialect.wrap_metric("REVENUE")

    def test_metric_result_column_name_upper_cases_inside_the_quotes(self):
        """
        Snowflake upper-cases the identifier when it labels the result column.

        Measured 2026-08-16 against a live semantic view whose second metric was
        created quoted as ``"gross revenue"`` — so its *stored* name really is
        lower-case with a space. Sent ``AGG("gross revenue")``, Snowflake answered
        a column named ``AGG("GROSS REVENUE")``.

        This is the case the committed recordings cannot reach: they carry only
        metric names that need no quoting, where an already-upper-case name is
        indistinguishable from a normalized one.
        """
        dialect = SnowflakeDialect()
        assert dialect.metric_result_column_name("gross revenue") == 'AGG("GROSS REVENUE")'

    def test_metric_result_column_name_diverges_from_wrap_metric_when_quoted(self):
        """
        The two spellings are not interchangeable on Snowflake after all.

        ``wrap_metric`` must send the stored spelling or the query fails with
        ``invalid identifier``; the result column arrives under the upper-cased
        one. Only a name that is already upper-case makes them agree.
        """
        dialect = SnowflakeDialect()
        assert dialect.wrap_metric("gross revenue") == 'AGG("gross revenue")'
        assert dialect.metric_result_column_name("gross revenue") != dialect.wrap_metric(
            "gross revenue"
        )


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

    def test_metric_result_column_name_is_lowercased_and_unquoted(self):
        """Databricks answers measure(revenue), not the MEASURE(`revenue`) it was sent."""
        dialect = DatabricksDialect()
        assert dialect.metric_result_column_name("revenue") == "measure(revenue)"

    def test_metric_result_column_name_folds_mixed_case(self):
        """The field name is lower-cased too, matching Databricks' unquoted folding."""
        dialect = DatabricksDialect()
        assert dialect.metric_result_column_name("Revenue") == "measure(revenue)"


class TestSupportsParameterizedQueries:
    """Capability flag default True, False only on Databricks."""

    def test_snowflake_supports_parameterized_queries(self):
        """SnowflakeDialect keeps the parameterized (?) path."""
        assert SnowflakeDialect().supports_parameterized_queries is True

    def test_duckdb_supports_parameterized_queries(self):
        """DuckDBDialect keeps the parameterized (?) path."""
        assert DuckDBDialect().supports_parameterized_queries is True

    def test_databricks_does_not_support_parameterized_queries(self):
        """DatabricksDialect opts out of bind params (ADBC driver gap)."""
        assert DatabricksDialect().supports_parameterized_queries is False


class TestRenderLiteralStandardSql:
    """DBX-01c: standard-SQL render_literal (base ABC via SnowflakeDialect)."""

    def test_string_doubles_single_quote(self):
        """Standard SQL escapes a single quote by doubling it."""
        assert SnowflakeDialect().render_literal("O'Reilly") == "'O''Reilly'"

    def test_plain_string(self):
        """A plain string is wrapped in single quotes."""
        assert SnowflakeDialect().render_literal("US") == "'US'"

    def test_none_renders_null(self):
        """None renders as the SQL NULL keyword (unquoted)."""
        assert SnowflakeDialect().render_literal(None) == "NULL"

    def test_bool_renders_uppercase(self):
        """Booleans render as uppercase TRUE/FALSE for standard SQL."""
        assert SnowflakeDialect().render_literal(True) == "TRUE"
        assert SnowflakeDialect().render_literal(False) == "FALSE"

    def test_int_renders_unquoted(self):
        """Integers render unquoted."""
        assert SnowflakeDialect().render_literal(5) == "5"

    def test_unsupported_type_raises_not_implemented(self):
        """An unsupported literal type fails loudly rather than mis-escaping."""
        with pytest.raises(NotImplementedError):
            SnowflakeDialect().render_literal({1, 2})

    def test_non_finite_float_raises(self):
        """inf/-inf/nan are not SQL numeric literals -- fail loudly."""
        for value in (float("inf"), float("-inf"), float("nan")):
            with pytest.raises(ValueError):
                SnowflakeDialect().render_literal(value)

    def test_date_literal(self):
        """A date renders as a typed DATE literal in ISO-8601 form."""
        assert SnowflakeDialect().render_literal(datetime.date(2024, 1, 31)) == "DATE '2024-01-31'"

    def test_naive_datetime_literal(self):
        """A naive datetime renders as TIMESTAMP and keeps its time of day."""
        value = datetime.datetime(2024, 1, 31, 10, 5)
        assert SnowflakeDialect().render_literal(value) == "TIMESTAMP '2024-01-31T10:05:00'"

    def test_aware_datetime_normalises_to_utc_z(self):
        """An aware datetime is converted to UTC and suffixed with Z."""
        tz = datetime.timezone(datetime.timedelta(hours=2))
        value = datetime.datetime(2024, 1, 31, 10, 5, tzinfo=tz)
        assert SnowflakeDialect().render_literal(value) == "TIMESTAMP '2024-01-31T08:05:00Z'"

    def test_datetime_microseconds_survive(self):
        """Sub-second precision reaches the literal unrounded."""
        value = datetime.datetime(2024, 1, 31, 10, 5, 3, 123456)
        assert ".123456" in SnowflakeDialect().render_literal(value)

    def test_decimal_literal_is_bare_fixed_point(self):
        """A Decimal renders as bare fixed-point digits, unquoted and uncast."""
        assert SnowflakeDialect().render_literal(Decimal("10.50")) == "10.50"

    def test_decimal_exponent_form_stays_decimal(self):
        """An exponent-form Decimal renders fixed-point, never as 1E+2."""
        assert SnowflakeDialect().render_literal(Decimal("1E+2")) == "100"

    def test_non_finite_decimal_raises(self):
        """NaN/Infinity Decimals have no SQL literal form -- fail loudly."""
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with pytest.raises(ValueError):
                SnowflakeDialect().render_literal(value)

    def test_date_literal_has_no_unescaped_quote(self):
        """A DATE literal carries exactly its two delimiting quotes."""
        rendered = SnowflakeDialect().render_literal(datetime.date(2024, 1, 31))
        assert rendered.count("'") == 2

    def test_timestamp_literal_has_no_unescaped_quote(self):
        """A TIMESTAMP literal carries exactly its two delimiting quotes."""
        tz = datetime.timezone(datetime.timedelta(hours=-5))
        value = datetime.datetime(2024, 1, 31, 10, 5, tzinfo=tz)
        rendered = SnowflakeDialect().render_literal(value)
        assert rendered.count("'") == 2

    def test_decimal_literal_is_digits_only(self):
        """A Decimal literal is digits, an optional sign and at most one point."""
        rendered = SnowflakeDialect().render_literal(Decimal("-1234.5678"))
        assert re.fullmatch(r"-?\d+(\.\d+)?", rendered) is not None


class TestRenderLiteralDatabricks:
    """DBX-01c: Spark-string render_literal (escape backslash first, then quote)."""

    def test_plain_string(self):
        """A plain string is wrapped in single quotes."""
        assert DatabricksDialect().render_literal("US") == "'US'"

    def test_single_quote_backslash_escaped(self):
        r"""Spark escapes a single quote with a backslash (\')."""
        assert DatabricksDialect().render_literal("O'Reilly") == "'O\\'Reilly'"

    def test_backslash_escaped_first(self):
        r"""A backslash is doubled (\\) -- escaped before the quote."""
        assert DatabricksDialect().render_literal("a\\b") == "'a\\\\b'"

    def test_backslash_then_quote_ordering(self):
        r"""Backslash is escaped before the quote so order does not corrupt output."""
        # value: a\'b  ->  backslash doubled, then quote backslash-escaped
        assert DatabricksDialect().render_literal("a\\'b") == "'a\\\\\\'b'"

    def test_injection_attempt_is_escaped(self):
        """An injection-style value stays inside the quoted literal."""
        result = DatabricksDialect().render_literal("'; DROP TABLE x; --")
        assert result == "'\\'; DROP TABLE x; --'"

    def test_non_finite_float_raises(self):
        """inf/-inf/nan are not SQL numeric literals -- fail loudly."""
        for value in (float("inf"), float("-inf"), float("nan")):
            with pytest.raises(ValueError):
                DatabricksDialect().render_literal(value)

    def test_none_renders_null(self):
        """None renders as the SQL NULL keyword (unquoted)."""
        assert DatabricksDialect().render_literal(None) == "NULL"

    def test_bool_renders_lowercase(self):
        """Booleans render as lowercase true/false for Spark SQL."""
        assert DatabricksDialect().render_literal(True) == "true"
        assert DatabricksDialect().render_literal(False) == "false"

    def test_int_renders_unquoted(self):
        """Integers render unquoted."""
        assert DatabricksDialect().render_literal(5) == "5"

    def test_unsupported_type_raises_not_implemented(self):
        """An unsupported literal type fails loudly rather than mis-escaping."""
        with pytest.raises(NotImplementedError):
            DatabricksDialect().render_literal({1, 2})

    def test_date_literal(self):
        """A date renders as a typed DATE literal in ISO-8601 form."""
        assert DatabricksDialect().render_literal(datetime.date(2024, 1, 31)) == "DATE '2024-01-31'"

    def test_naive_datetime_literal(self):
        """A naive datetime renders as TIMESTAMP and keeps its time of day."""
        value = datetime.datetime(2024, 1, 31, 10, 5)
        assert DatabricksDialect().render_literal(value) == "TIMESTAMP '2024-01-31T10:05:00'"

    def test_aware_datetime_normalises_to_utc_z(self):
        """An aware datetime is converted to UTC and suffixed with Z."""
        tz = datetime.timezone(datetime.timedelta(hours=2))
        value = datetime.datetime(2024, 1, 31, 10, 5, tzinfo=tz)
        assert DatabricksDialect().render_literal(value) == "TIMESTAMP '2024-01-31T08:05:00Z'"

    def test_datetime_microseconds_survive(self):
        """Sub-second precision reaches the literal unrounded."""
        value = datetime.datetime(2024, 1, 31, 10, 5, 3, 123456)
        assert ".123456" in DatabricksDialect().render_literal(value)

    def test_decimal_literal_is_bare_fixed_point(self):
        """A Decimal renders as bare fixed-point digits, unquoted and uncast."""
        assert DatabricksDialect().render_literal(Decimal("10.50")) == "10.50"

    def test_decimal_exponent_form_stays_decimal(self):
        """An exponent-form Decimal renders fixed-point, never as 1E+2."""
        assert DatabricksDialect().render_literal(Decimal("1E+2")) == "100"

    def test_non_finite_decimal_raises(self):
        """NaN/Infinity Decimals have no SQL literal form -- fail loudly."""
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with pytest.raises(ValueError):
                DatabricksDialect().render_literal(value)

    def test_date_literal_has_no_unescaped_quote(self):
        """A DATE literal carries exactly its two delimiting quotes."""
        rendered = DatabricksDialect().render_literal(datetime.date(2024, 1, 31))
        assert rendered.count("'") == 2

    def test_timestamp_literal_has_no_unescaped_quote(self):
        """A TIMESTAMP literal carries exactly its two delimiting quotes."""
        tz = datetime.timezone(datetime.timedelta(hours=-5))
        value = datetime.datetime(2024, 1, 31, 10, 5, tzinfo=tz)
        rendered = DatabricksDialect().render_literal(value)
        assert rendered.count("'") == 2

    def test_decimal_literal_is_digits_only(self):
        """A Decimal literal is digits, an optional sign and at most one point."""
        rendered = DatabricksDialect().render_literal(Decimal("-1234.5678"))
        assert re.fullmatch(r"-?\d+(\.\d+)?", rendered) is not None


class TestViewNameNormalization:
    """
    View names are folded through the dialect like column identifiers.

    A bare ``view="sales_view"`` resolves against a standard Snowflake view
    (created unquoted, stored UPPERCASE) and a Databricks view (stored
    lowercase). Schema-qualified names are quoted per-part. A pre-quoted
    segment is the escape hatch for a case-sensitive name.
    """

    def test_snowflake_quote_table_name_folds_to_uppercase(self):
        """Bare segment is folded to UPPERCASE then quoted for Snowflake."""
        assert SnowflakeDialect().quote_table_name("sales_view") == '"SALES_VIEW"'

    def test_snowflake_quote_table_name_qualified_per_part(self):
        """Schema-qualified names quote each segment, not the whole string."""
        assert (
            SnowflakeDialect().quote_table_name("my_schema.sales_view")
            == '"MY_SCHEMA"."SALES_VIEW"'
        )

    def test_snowflake_quote_table_name_preserves_prequoted_segment(self):
        """An already-quoted segment is preserved verbatim (escape hatch)."""
        assert SnowflakeDialect().quote_table_name('"sales_view"') == '"sales_view"'
        assert SnowflakeDialect().quote_table_name('analytics."My_View"') == '"ANALYTICS"."My_View"'

    def test_databricks_quote_table_name_folds_to_lowercase(self):
        """Databricks folds to lowercase then backtick-quotes."""
        assert DatabricksDialect().quote_table_name("Sales_View") == "`sales_view`"

    def test_qualified_view_name_in_from_clause(self):
        """A schema-qualified model view name is quoted per-part in FROM."""
        from semolina import Metric, SemanticView

        class QualifiedSales(SemanticView, view="analytics.sales_view"):
            revenue = Metric()

        query = QualifiedSales.query().metrics(QualifiedSales.revenue)
        sql = SQLBuilder(SnowflakeDialect()).build_select(query)
        assert sql == 'SELECT AGG("REVENUE") AS "revenue"\nFROM "ANALYTICS"."SALES_VIEW"'


class TestEachDialectRendersTheFullStatement:
    """The same fully built query, as each dialect renders it."""

    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            (
                "snowflake",
                'SELECT AGG("REVENUE") AS "revenue", AGG("COST") AS "cost", '
                '"COUNTRY" AS "country", "REGION" AS "region"\n'
                'FROM "SALES_VIEW"\n'
                "WHERE (\"COUNTRY\" = 'US' OR \"COUNTRY\" = 'CA')\n"
                "GROUP BY ALL\n"
                'ORDER BY AGG("REVENUE") DESC NULLS FIRST, "COUNTRY" ASC\n'
                "LIMIT 100",
            ),
            (
                "databricks",
                "SELECT MEASURE(`revenue`) AS `revenue`, MEASURE(`cost`) AS `cost`, "
                "`country` AS `country`, `region` AS `region`\n"
                "FROM `sales_view`\n"
                "WHERE (`country` = 'US' OR `country` = 'CA')\n"
                "GROUP BY ALL\n"
                "ORDER BY MEASURE(`revenue`) DESC NULLS FIRST, `country` ASC\n"
                "LIMIT 100",
            ),
            (
                "duckdb",
                'SELECT "revenue" AS "revenue", "cost" AS "cost", '
                '"country" AS "country", "region" AS "region"\n'
                "FROM semantic_view('sales_view', dimensions := ['country', 'region'], "
                "metrics := ['revenue', 'cost'], "
                "where_clause := '(\"country\" = ''US'' OR \"country\" = ''CA'')')\n"
                'ORDER BY "revenue" DESC NULLS FIRST, "country" ASC\n'
                "LIMIT 100",
            ),
        ],
    )
    def test_full_chain(self, dialect: str, expected: str):
        """
        Quoting, metric wrapping and name folding differ, and DuckDB's filter moves into the call.

        The select list is the same on all three: every field under its Python name, metrics
        first.
        """
        query = (
            Sales.query()
            .metrics(Sales.revenue, Sales.cost)
            .dimensions(Sales.country, Sales.region)
            .where((Sales.country == "US") | (Sales.country == "CA"))
            .order_by(Sales.revenue.desc(NullsOrdering.FIRST), Sales.country.asc())
            .limit(100)
        )

        assert query.to_sql(dialect) == expected


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
# Dialect.placeholder, WHERE compiler, parameterization
# ---------------------------------------------------------------------------


class TestDialectPlaceholder:
    """Test Dialect.placeholder property returns backend-specific placeholder."""

    def test_snowflake_placeholder(self):
        """SnowflakeDialect.placeholder should return ?."""
        assert SnowflakeDialect().placeholder == "?"

    def test_databricks_placeholder(self):
        """DatabricksDialect.placeholder should return ?."""
        assert DatabricksDialect().placeholder == "?"


class TestWhereClauseCompiler:
    """Every node type compiles to its condition, read off a real ``.where()`` query."""

    # -- Leaf lookups (15 types) -----------------------------------------------

    def test_compile_exact(self):
        """Exact(f, v) -> '{quote(f)} = {ph}', [v]."""
        sql, params = where_clause(Exact("country", "US"))
        assert sql == '"COUNTRY" = ?'
        assert params == ["US"]

    def test_compile_not_equal(self):
        """NotEqual(f, v) -> '{quote(f)} != {ph}', [v]."""
        sql, params = where_clause(NotEqual("country", "US"))
        assert sql == '"COUNTRY" != ?'
        assert params == ["US"]

    def test_compile_gt(self):
        """Gt(f, v) -> '{quote(f)} > {ph}', [v]."""
        sql, params = where_clause(Gt("revenue", 1000))
        assert sql == '"REVENUE" > ?'
        assert params == [1000]

    def test_compile_gte(self):
        """Gte(f, v) -> '{quote(f)} >= {ph}', [v]."""
        sql, params = where_clause(Gte("revenue", 500))
        assert sql == '"REVENUE" >= ?'
        assert params == [500]

    def test_compile_lt(self):
        """Lt(f, v) -> '{quote(f)} < {ph}', [v]."""
        sql, params = where_clause(Lt("revenue", 100))
        assert sql == '"REVENUE" < ?'
        assert params == [100]

    def test_compile_lte(self):
        """Lte(f, v) -> '{quote(f)} <= {ph}', [v]."""
        sql, params = where_clause(Lte("revenue", 50))
        assert sql == '"REVENUE" <= ?'
        assert params == [50]

    def test_compile_in_with_values(self):
        """In(f, [a,b,c]) -> '{quote(f)} IN ({ph}, {ph}, {ph})', [a, b, c]."""
        sql, params = where_clause(In("country", ["US", "CA", "UK"]))
        assert sql == '"COUNTRY" IN (?, ?, ?)'
        assert params == ["US", "CA", "UK"]

    def test_compile_in_single_value(self):
        """In(f, [a]) -> '{quote(f)} IN ({ph})', [a]."""
        sql, params = where_clause(In("country", ["US"]))
        assert sql == '"COUNTRY" IN (?)'
        assert params == ["US"]

    def test_compile_in_empty(self):
        """In(f, []) -> '1 = 0', [] (always false, Django precedent)."""
        sql, params = where_clause(In("country", []))
        assert sql == "1 = 0"
        assert params == []

    def test_compile_in_from_a_generator(self):
        """
        A generator's values are all bound.

        A generator can be read only once. Compiling the placeholders and then the parameters
        from it separately would leave the placeholders with no values behind them.
        """
        sql, params = where_clause(Sales.country.in_(c for c in ["US", "CA"]))
        assert sql == '"COUNTRY" IN (?, ?)'
        assert params == ["US", "CA"]

    @pytest.mark.parametrize(
        "values",
        [
            lambda: ["US", "CA"],
            lambda: ("US", "CA"),
            lambda: {"US": 1, "CA": 2},
            lambda: iter(["US", "CA"]),
            lambda: (c for c in ["US", "CA"]),
        ],
        ids=["list", "tuple", "dict-keys", "iterator", "generator"],
    )
    def test_compile_in_binds_one_parameter_per_placeholder(
        self, values: Callable[[], Iterable[str]]
    ):
        """Whatever iterable ``in_()`` is given, the statement has a value for every ``?``."""
        sql, params = where_clause(Sales.country.in_(values()))
        assert sql.count("?") == len(params) == 2

    def test_compile_between(self):
        """Between(f, (lo, hi)) -> '{quote(f)} BETWEEN {ph} AND {ph}', [lo, hi]."""
        sql, params = where_clause(Between("revenue", (100, 500)))
        assert sql == '"REVENUE" BETWEEN ? AND ?'
        assert params == [100, 500]

    def test_compile_is_null_true(self):
        """IsNull(f, True) -> '{quote(f)} IS NULL', []."""
        sql, params = where_clause(IsNull("country", True))
        assert sql == '"COUNTRY" IS NULL'
        assert params == []

    def test_compile_is_null_false(self):
        """IsNull(f, False) -> '{quote(f)} IS NOT NULL', []."""
        sql, params = where_clause(IsNull("country", False))
        assert sql == '"COUNTRY" IS NOT NULL'
        assert params == []

    def test_compile_like(self):
        """Like(f, v) -> '{quote(f)} LIKE {ph}', [v]."""
        sql, params = where_clause(Like("name", "%test%"))
        assert sql == '"NAME" LIKE ?'
        assert params == ["%test%"]

    def test_compile_ilike(self):
        """ILike(f, v) -> '{quote(f)} ILIKE {ph}', [v]."""
        sql, params = where_clause(ILike("name", "%test%"))
        assert sql == '"NAME" ILIKE ?'
        assert params == ["%test%"]

    def test_compile_starts_with(self):
        """StartsWith(f, v) -> '{quote(f)} LIKE {ph}', [v + '%']."""
        sql, params = where_clause(StartsWith("name", "test"))
        assert sql == '"NAME" LIKE ?'
        assert params == ["test%"]

    def test_compile_istarts_with(self):
        """IStartsWith(f, v) -> '{quote(f)} ILIKE {ph}', [v + '%']."""
        sql, params = where_clause(IStartsWith("name", "test"))
        assert sql == '"NAME" ILIKE ?'
        assert params == ["test%"]

    def test_compile_ends_with(self):
        """EndsWith(f, v) -> '{quote(f)} LIKE {ph}', ['%' + v]."""
        sql, params = where_clause(EndsWith("name", "test"))
        assert sql == '"NAME" LIKE ?'
        assert params == ["%test"]

    def test_compile_iends_with(self):
        """IEndsWith(f, v) -> '{quote(f)} ILIKE {ph}', ['%' + v]."""
        sql, params = where_clause(IEndsWith("name", "test"))
        assert sql == '"NAME" ILIKE ?'
        assert params == ["%test"]

    def test_compile_iexact(self):
        """IExact(f, v) -> '{quote(f)} ILIKE {ph}', [v] (no wildcards)."""
        sql, params = where_clause(IExact("name", "Test"))
        assert sql == '"NAME" ILIKE ?'
        assert params == ["Test"]

    # -- Composite nodes -------------------------------------------------------

    def test_compile_and(self):
        """And(l, r) -> '({l_sql} AND {r_sql})', l_params + r_params."""
        pred = Exact("country", "US") & Gt("revenue", 1000)
        sql, params = where_clause(pred)
        assert sql == '("COUNTRY" = ? AND "REVENUE" > ?)'
        assert params == ["US", 1000]

    def test_compile_or(self):
        """Or(l, r) -> '({l_sql} OR {r_sql})', l_params + r_params."""
        pred = Exact("country", "US") | Exact("country", "CA")
        sql, params = where_clause(pred)
        assert sql == '("COUNTRY" = ? OR "COUNTRY" = ?)'
        assert params == ["US", "CA"]

    def test_compile_not(self):
        """Not(i) -> 'NOT ({i_sql})', i_params."""
        pred = ~Exact("country", "US")
        sql, params = where_clause(pred)
        assert sql == 'NOT ("COUNTRY" = ?)'
        assert params == ["US"]

    def test_compile_nested_and_or_not(self):
        """(a & b) | ~c compiles correctly."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        c = Exact("region", "West")
        pred = (a & b) | ~c
        sql, params = where_clause(pred)
        assert sql == '(("COUNTRY" = ? AND "REVENUE" > ?) OR NOT ("REGION" = ?))'
        assert params == ["US", 1000, "West"]

    def test_compile_double_not(self):
        """~~predicate -> NOT (NOT ({sql}))."""
        pred = ~~Exact("country", "US")
        sql, params = where_clause(pred)
        assert sql == 'NOT (NOT ("COUNTRY" = ?))'
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
        _sql, params = where_clause(pred)
        assert params == [1, 2, 3]

    # -- Dialect-specific placeholders -----------------------------------------

    # -- Error cases -----------------------------------------------------------

    def test_unknown_lookup_raises_not_implemented(self):
        """Unknown Lookup subclass raises NotImplementedError."""

        class CustomLookup(Lookup[str]):
            """A custom lookup that the compiler doesn't know about."""

        pred = CustomLookup("field", "value")
        with pytest.raises(NotImplementedError):
            where_clause(pred)

    def test_non_predicate_raises_type_error(self):
        """Non-Predicate input raises TypeError."""
        with pytest.raises(TypeError):
            where_clause("not a predicate")  # type: ignore[arg-type]


class TestBoundVersusInlinedParameters:
    """
    Snowflake binds WHERE values as ``?``, Databricks inlines them, and DuckDB binds one string.

    DuckDB's bound string is the dimension filter's ``where_clause``, with its values rendered
    into it as literals.

    Each case is the whole statement a warehouse receives plus its bound parameters, so a
    value that leaked into a bound template, or a placeholder left behind in an inlined one,
    fails the comparison without needing its own assertion.
    """

    @pytest.mark.parametrize(
        ("dialect", "expected_sql", "expected_params"),
        [
            (
                "snowflake",
                'SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country"\n'
                'FROM "SALES_VIEW"\n'
                'WHERE "COUNTRY" = ?\n'
                "GROUP BY ALL",
                ["US"],
            ),
            (
                "duckdb",
                'SELECT "revenue" AS "revenue", "country" AS "country"\n'
                "FROM semantic_view('sales_view', dimensions := ['country'], "
                "metrics := ['revenue'], where_clause := ?)",
                ["\"country\" = 'US'"],
            ),
            (
                "databricks",
                "SELECT MEASURE(`revenue`) AS `revenue`, `country` AS `country`\n"
                "FROM `sales_view`\n"
                "WHERE `country` = 'US'\nGROUP BY ALL",
                [],
            ),
        ],
    )
    def test_a_filtered_query_per_dialect(
        self, dialect: str, expected_sql: str, expected_params: list[object]
    ):
        """The same filtered query, as each dialect sends it."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
        )
        builder = resolve_dialect(dialect).create_builder()

        assert builder.build_select_with_params(query) == (expected_sql, expected_params)

    def test_a_query_without_filters_binds_nothing(self):
        """No WHERE clause, and no parameters."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = resolve_dialect("snowflake").create_builder()

        assert builder.build_select_with_params(query) == (
            'SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country"\n'
            'FROM "SALES_VIEW"\n'
            "GROUP BY ALL",
            [],
        )

    def test_params_are_accumulated_in_order(self):
        """A composite filter binds its values in reading order."""
        condition, params = where_clause(Exact("country", "US") & Gt("revenue", 500))

        assert condition == '("COUNTRY" = ? AND "REVENUE" > ?)'
        assert params == ["US", 500]

    @pytest.mark.parametrize(
        ("predicate", "condition"),
        [
            (In("country", ["US", "CA"]), "`country` IN ('US', 'CA')"),
            (Exact("country", "O'Reilly"), "`country` = 'O\\'Reilly'"),
            # A '?' inside a value must not be read as a placeholder, in a list or beside a
            # second condition.
            (In("country", ["a?b", "CA"]), "`country` IN ('a?b', 'CA')"),
            (
                Exact("country", "a?b") & Exact("region", "WEST"),
                "(`country` = 'a?b' AND `region` = 'WEST')",
            ),
            (Exact("date_key", datetime.date(2024, 1, 31)), "`date_key` = DATE '2024-01-31'"),
        ],
        ids=["in-list", "quote", "placeholder-in-list", "placeholder-then-condition", "date"],
    )
    def test_databricks_inlines_each_value_safely(self, predicate: object, condition: str):
        """Every value is rendered as an escaped literal, and nothing is left to bind."""
        assert where_clause(predicate, "databricks") == (condition, [])

    def test_build_select_renders_parameters_inline(self):
        """``build_select()`` is the display form: the bound values rendered in place."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
        )

        assert SQLBuilder(SnowflakeDialect()).build_select(query) == (
            'SELECT AGG("REVENUE") AS "revenue", "COUNTRY" AS "country"\n'
            'FROM "SALES_VIEW"\n'
            "WHERE \"COUNTRY\" = 'US'\n"
            "GROUP BY ALL"
        )


class TestRenderInline:
    """Test render_inline substitutes params with repr()."""

    def test_render_inline_single_param(self):
        """render_inline substitutes single param with repr()."""
        builder = SQLBuilder(SnowflakeDialect())
        result = builder.render_inline('"country" = ?', ["US"])
        assert result == "\"country\" = 'US'"

    def test_render_inline_multiple_params(self):
        """render_inline substitutes multiple params in order."""
        builder = SQLBuilder(SnowflakeDialect())
        result = builder.render_inline(
            '"country" = ? AND "revenue" > ?',
            ["US", 1000],
        )
        assert result == '"country" = \'US\' AND "revenue" > 1000'

    def test_render_inline_no_params(self):
        """render_inline with no params returns unchanged SQL."""
        builder = SQLBuilder(SnowflakeDialect())
        result = builder.render_inline("SELECT 1", [])
        assert result == "SELECT 1"

    def test_render_inline_databricks_placeholder(self):
        """render_inline works with ? placeholder for Databricks."""
        builder = SQLBuilder(DatabricksDialect())
        result = builder.render_inline("`country` = ?", ["US"])
        assert result == "`country` = 'US'"


# ---------------------------------------------------------------------------
# normalize_identifier, and how source= bypasses it
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


class TestWhereClauseNormalization:
    """Test WHERE clause field_name normalization through dialect."""

    def test_snowflake_where_normalizes_field_name_to_uppercase(self):
        """Snowflake WHERE clause normalizes Python field_name to UPPERCASE."""
        sql, params = where_clause(Exact("order_id", "ORD-001"))
        assert sql == '"ORDER_ID" = ?'
        assert params == ["ORD-001"]

    def test_databricks_where_normalizes_field_name_to_lowercase(self):
        """Databricks WHERE clause normalizes Python field_name to lowercase, value inlined."""
        sql, params = where_clause(Exact("ORDER_ID", "ORD-001"), "databricks")
        assert sql == "`order_id` = 'ORD-001'"
        assert params == []


class TestWhereClauseSourceOverride:
    """Regression tests: source= override propagates through WHERE clause compiler."""

    def test_metric_with_source_uses_source_in_where(self):
        """
        ``source=`` is the column selected and filtered on, verbatim and unfolded.

        The result still comes back under the Python attribute name: the alias is the one
        place that name appears, so a renamed warehouse column needs no change to the code
        that reads the row.
        """

        class MyView(SemanticView, view="my_view"):
            revenue_usd_field = Metric[int](source="revenue_usd")

        query = (
            MyView.query().metrics(MyView.revenue_usd_field).where(MyView.revenue_usd_field > 100)
        )

        assert query.to_sql() == (
            'SELECT AGG("revenue_usd") AS "revenue_usd_field"\nFROM "MY_VIEW"\n'
            'WHERE "revenue_usd" > 100'
        )

    @pytest.mark.parametrize(
        ("dialect", "expected"),
        [
            ("snowflake", 'SELECT "COUNTRY_CODE" AS "country"\nFROM "V"\nGROUP BY ALL'),
            ("databricks", "SELECT `COUNTRY_CODE` AS `country`\nFROM `v`\nGROUP BY ALL"),
        ],
    )
    def test_source_is_verbatim_on_every_dialect(self, dialect: str, expected: str):
        """A ``source=`` column is not folded by the dialect, and returns under the field name."""

        class V(SemanticView, view="v"):
            country = Dimension[str](source="COUNTRY_CODE")

        assert V.query().dimensions(V.country).to_sql(dialect) == expected

    def test_field_without_source_where_still_normalized(self):
        """Field without source= still gets dialect normalization in WHERE."""
        sql, params = where_clause(Exact("revenue", "US"))
        assert sql == '"REVENUE" = ?'
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

    def test_metric_result_column_name_is_bare(self):
        """semantic_view() returns the metric under its own name, unwrapped and unquoted."""
        assert DuckDBDialect().metric_result_column_name("revenue") == "revenue"

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


# ---------------------------------------------------------------------------
# DuckDB SQL Builder tests
# ---------------------------------------------------------------------------


class TestDuckDBSQLBuilder:
    """
    Test DuckDBSQLBuilder generates correct semantic_view() SQL.

    The outer ``SELECT`` names every selected field and aliases it to its Python name (D2-1),
    so the result keys match Snowflake's and Databricks'. Dimension and fact filters go into
    the call as a bound ``where_clause``, metric filters into an outer ``WHERE`` (D2-3).
    """

    def test_grouped_query_sql(self):
        """Dimensions + metrics: each is projected under its field name, metrics first."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue'])"
        )
        assert params == []

    def test_facts_only_query(self):
        """Facts only produces semantic_view() with facts arg."""
        query = Sales.query().dimensions(Sales.unit_price)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "unit_price" AS "unit_price"\n'
            "FROM semantic_view('sales_view', facts := ['unit_price'])"
        )
        assert params == []

    def test_facts_and_dimensions_query(self):
        """Dimensions + facts are projected in the order they were selected."""
        query = Sales.query().dimensions(Sales.country, Sales.unit_price)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "country" AS "country", "unit_price" AS "unit_price"\n'
            "FROM semantic_view('sales_view', "
            "dimensions := ['country'], facts := ['unit_price'])"
        )
        assert params == []

    def test_a_source_override_is_requested_by_source_and_returned_by_field_name(self):
        """``source=`` names the member asked for; the alias is still the field's own name."""

        class Renamed(SemanticView, view="sales_view"):
            revenue = Metric[int](source="net_revenue")
            country = Dimension[str](source="COUNTRY_CODE")

        query = Renamed.query().metrics(Renamed.revenue).dimensions(Renamed.country)
        sql, _params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == (
            'SELECT "net_revenue" AS "revenue", "COUNTRY_CODE" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['COUNTRY_CODE'], "
            "metrics := ['net_revenue'])"
        )

    def test_facts_and_metrics_raises(self):
        """ValueError when both facts and metrics are present."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.unit_price)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        with pytest.raises(ValueError, match="combining facts and metrics"):
            builder.build_select_with_params(query)

    def test_where_clause(self):
        """A dimension filter goes into the call as one bound ``where_clause`` string."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue'], where_clause := ?)"
        )
        assert params == ["\"country\" = 'US'"]

    def test_where_dimension_not_selected_filters_without_regrouping(self):
        """
        A filter on an unselected dimension does not add it to ``dimensions``.

        Adding it would regroup the result by it (ALIAS-05). ``where_clause`` is applied
        before aggregation, so the dimension never has to be returned.
        """
        query = Sales.query().metrics(Sales.revenue).where(Sales.country == "US")
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue"\n'
            "FROM semantic_view('sales_view', metrics := ['revenue'], where_clause := ?)"
        )
        assert params == ["\"country\" = 'US'"]

    def test_a_whole_or_of_dimensions_stays_one_where_clause(self):
        """A filter over dimensions only is not split, whatever its shape."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.region)
            .where((Sales.country == "US") | ~(Sales.country == "CA"))
        )
        _sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert params == ["(\"country\" = 'US' OR NOT (\"country\" = 'CA'))"]

    def test_where_clause_values_are_rendered_as_escaped_literals(self):
        """A quote in a value is doubled inside the bound clause, never left to close it."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .where(Sales.country.in_(["O'Neill", "x' OR 1=1 --"]))
        )
        _sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert params == ["\"country\" IN ('O''Neill', 'x'' OR 1=1 --')"]

    def test_a_fact_filter_goes_into_the_where_clause(self):
        """Facts are row-level, so a fact filter is pre-aggregation too."""
        query = Sales.query().dimensions(Sales.unit_price).where(Sales.unit_price > 5)
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == (
            'SELECT "unit_price" AS "unit_price"\n'
            "FROM semantic_view('sales_view', facts := ['unit_price'], where_clause := ?)"
        )
        assert params == ['"unit_price" > 5']

    def test_a_metric_filter_goes_into_an_outer_where(self):
        """The extension refuses a metric in ``where_clause``; an outer WHERE is HAVING."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.revenue > 100)
        )
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == DUCKDB_SALES + '\nWHERE "revenue" > ?'
        assert params == [100]

    def test_an_unselected_metric_filter_is_requested_but_not_projected(self):
        """A metric does not group, so requesting it changes no grain."""
        query = (
            Sales.query().metrics(Sales.revenue).dimensions(Sales.country).where(Sales.cost > 100)
        )
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue', 'cost'])\n"
            'WHERE "cost" > ?'
        )
        assert params == [100]

    def test_a_top_level_and_splits_into_where_clause_and_outer_where(self):
        """Each conjunct goes where it can be applied; the clause is bound first."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where((Sales.country == "US") & (Sales.revenue > 100) & (Sales.region == "West"))
        )
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue'], where_clause := ?)\n"
            'WHERE "revenue" > ?'
        )
        assert params == ["(\"country\" = 'US' AND \"region\" = 'West')", 100]

    @pytest.mark.parametrize(
        "predicate",
        [
            (Sales.country == "US") | (Sales.revenue > 100),
            ~((Sales.country == "US") & (Sales.revenue > 100)),
            (Sales.region == "West") & ((Sales.country == "US") | (Sales.revenue > 100)),
        ],
        ids=["or", "not-and", "and-of-mixed-or"],
    )
    def test_a_dimension_and_a_metric_under_or_or_not_is_refused(self, predicate: object):
        """
        Such a filter has no pre-aggregation and post-aggregation halves to split into.

        The error names both kinds of field so the reader can see which part to move.
        """
        query = Sales.query().metrics(Sales.revenue).where(predicate)  # pyright: ignore[reportArgumentType]
        builder = DuckDBSQLBuilder(DuckDBDialect())
        with pytest.raises(ValueError, match=r"country.*revenue|revenue.*country"):
            builder.build_select_with_params(query)

    @pytest.mark.parametrize(
        ("predicate", "clause", "outer"),
        [
            (
                (Sales.country == "US") & ((Sales.region == "West") & (Sales.unit_price > 1)),
                '("country" = \'US\' AND ("region" = \'West\' AND "unit_price" > 1))',
                None,
            ),
            (
                (Sales.revenue > 1) & ((Sales.cost > 2) & (Sales.revenue < 9)),
                None,
                '("revenue" > ? AND ("cost" > ? AND "revenue" < ?))',
            ),
        ],
        ids=["dimensions", "metrics"],
    )
    def test_a_filter_of_one_kind_is_sent_as_written(
        self, predicate: object, clause: str | None, outer: str | None
    ):
        """Only a filter that mixes both kinds is split; the rest keep their grouping."""
        query = Sales.query().metrics(Sales.revenue).where(predicate)  # pyright: ignore[reportArgumentType]
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        if clause is not None:
            assert params == [clause]
            assert "\nWHERE" not in sql
        if outer is not None:
            assert sql.split("\n")[-1] == f"WHERE {outer}"
            assert "where_clause" not in sql

    def test_a_query_without_a_bound_model_still_routes_a_metric_filter(self):
        """
        A query built without ``Model.query()`` finds its model through its fields.

        Without one the metric filter would reach ``where_clause``, which the extension
        refuses.
        """
        from semolina.query import _Query  # pyright: ignore[reportPrivateUsage]

        query = _Query().metrics(Sales.revenue).where(Sales.revenue > 100)
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue"\n'
            "FROM semantic_view('sales_view', metrics := ['revenue'])\n"
            'WHERE "revenue" > ?'
        )
        assert params == [100]

    def test_a_metric_filter_on_a_facts_query_is_refused(self):
        """A metric filter needs the metric, and facts and metrics cannot be combined."""
        query = Sales.query().dimensions(Sales.unit_price).where(Sales.revenue > 100)
        with pytest.raises(ValueError, match="combining facts and metrics"):
            DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)

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
        assert sql == DUCKDB_SALES + '\nORDER BY "revenue" DESC'

    def test_order_by_dimension(self):
        """ORDER BY dimension uses plain quoted identifier."""
        query = (
            Sales.query().metrics(Sales.revenue).dimensions(Sales.country).order_by(Sales.country)
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert sql == DUCKDB_SALES + '\nORDER BY "country" ASC'

    def test_order_by_an_unselected_metric_is_requested_but_not_projected(self):
        """The outer ORDER BY can only see what the call returns, so the metric is asked for."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.cost.desc())
        )
        sql, params = DuckDBSQLBuilder(DuckDBDialect()).build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue', 'cost'])\n"
            'ORDER BY "cost" DESC'
        )
        assert params == []

    def test_limit(self):
        """LIMIT N as outer SQL."""
        query = Sales.query().metrics(Sales.revenue).dimensions(Sales.country).limit(10)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert sql == DUCKDB_SALES + "\nLIMIT 10"

    def test_full_query_with_where_order_limit(self):
        """Full query with WHERE + ORDER BY + LIMIT produces correct multi-line SQL."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where((Sales.country == "US") & (Sales.revenue > 10))
            .order_by(Sales.revenue.desc())
            .limit(10)
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        expected = (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', "
            "dimensions := ['country'], metrics := ['revenue'], where_clause := ?)\n"
            'WHERE "revenue" > ?\n'
            'ORDER BY "revenue" DESC\n'
            "LIMIT 10"
        )
        assert sql == expected
        assert params == ["\"country\" = 'US'", 10]

    def test_multiple_dimensions_and_metrics(self):
        """Multiple dimensions and metrics are listed correctly."""
        query = (
            Sales.query().metrics(Sales.revenue, Sales.cost).dimensions(Sales.country, Sales.region)
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "cost" AS "cost", '
            '"country" AS "country", "region" AS "region"\n'
            "FROM semantic_view('sales_view', dimensions := ['country', 'region'], "
            "metrics := ['revenue', 'cost'])"
        )

    def test_build_select_renders_inline(self):
        """
        build_select() shows the bound clause as the SQL string literal it is sent as.

        ``repr()`` would show it with backslash escapes, which is not SQL: the displayed
        statement must be one DuckDB would run.
        """
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .where(Sales.country == "US")
        )
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql = builder.build_select(query)
        assert sql == (
            'SELECT "revenue" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'], "
            "metrics := ['revenue'], where_clause := '\"country\" = ''US''')"
        )

    def test_dimensions_only_query(self):
        """Dimensions only (no metrics, no facts) produces correct SQL."""
        query = Sales.query().dimensions(Sales.country)
        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(query)
        assert sql == (
            'SELECT "country" AS "country"\n'
            "FROM semantic_view('sales_view', dimensions := ['country'])"
        )
        assert params == []


class TestOrderByAnUnselectedField:
    """
    Ordering by a dimension the query does not select is refused on every dialect (D2-4).

    On DuckDB it would have to be requested from ``semantic_view()``, which regroups the
    result by it; the outer ``ORDER BY`` cannot see it otherwise. On Snowflake and Databricks
    an aggregate query cannot order by a column it does not group by. A metric does not group,
    so ordering by an unselected metric stays allowed.
    """

    @pytest.mark.parametrize("dialect", ["snowflake", "databricks", "duckdb"])
    def test_an_unselected_dimension_is_refused(self, dialect: str):
        """The error names the field and says to select it."""
        query = Sales.query().metrics(Sales.revenue).order_by(Sales.country)
        builder = resolve_dialect(dialect).create_builder()
        with pytest.raises(ValueError, match=r"Sales\.country.*\.dimensions\(\)"):
            builder.build_select_with_params(query)

    @pytest.mark.parametrize("dialect", ["snowflake", "databricks", "duckdb"])
    def test_an_unselected_fact_is_refused(self, dialect: str):
        """A fact is row-level, so it is refused like a dimension."""
        query = Sales.query().dimensions(Sales.country).order_by(Sales.unit_price.desc())
        builder = resolve_dialect(dialect).create_builder()
        with pytest.raises(ValueError, match=r"Sales\.unit_price"):
            builder.build_select_with_params(query)

    def test_to_sql_refuses_it_too(self):
        """The display path builds the same statement, so it refuses the same query."""
        query = Sales.query().metrics(Sales.revenue).order_by(Sales.region.desc())
        with pytest.raises(ValueError, match=r"Sales\.region"):
            query.to_sql()

    @pytest.mark.parametrize(
        ("dialect", "order_by"),
        [
            ("snowflake", 'ORDER BY AGG("COST") DESC'),
            ("databricks", "ORDER BY MEASURE(`cost`) DESC"),
            ("duckdb", 'ORDER BY "cost" DESC'),
        ],
    )
    def test_an_unselected_metric_is_allowed(self, dialect: str, order_by: str):
        """The statement orders by the metric's expression without selecting it."""
        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .order_by(Sales.cost.desc())
        )
        sql, _params = resolve_dialect(dialect).create_builder().build_select_with_params(query)
        assert sql.split("\n")[-1] == order_by
        assert 'AS "cost"' not in sql
        assert "AS `cost`" not in sql


def outside_string_literals(sql: str) -> str:
    """
    Replace every single-quoted SQL string literal in ``sql`` with ``<literal>``.

    Reduces an injection assertion to the property that actually matters: what the parser
    would see as *SQL* once the literals are removed. Counting substrings does not work,
    because a payload that stayed safely inside its literal still contains the words
    ``FROM`` and ``read_csv``.

    The pattern consumes a doubled ``''`` as literal content, which is exactly the escape
    :func:`semolina.engines.sql.sql_str_literal` produces -- so an unescaped quote leaves
    its payload outside a ``<literal>`` marker and the assertion catches it.

    Args:
        sql: A SQL string.

    Returns:
        The same string with each literal collapsed to a marker.
    """
    return re.sub(r"'(?:[^']|'')*'", "<literal>", sql)


def from_line(sql: str) -> str:
    """
    Return the ``FROM`` line of a built statement.

    Args:
        sql: A statement built one clause per line.

    Returns:
        The line that starts with ``FROM``.
    """
    return next(line for line in sql.split("\n") if line.startswith("FROM "))


class TestDuckDBSemanticViewStringLiterals:
    """
    Nothing interpolated into ``semantic_view(...)`` can leave its string literal.

    ``semantic_view()`` takes its view name and every field name as SQL *string literals*,
    not as identifiers, so they cannot be parameter-bound and are interpolated. Field names
    were user-typed text until ``semolina codegen --check`` began feeding the warehouse
    catalogue's own answer back in, which makes a quote in a catalogue name reach a
    statement rather than only a model file.
    """

    def test_a_quote_in_a_source_override_cannot_open_a_new_clause(self):
        class Injected(SemanticView, view="v"):
            country = Dimension[str](source="x') FROM read_csv('/etc/passwd') --")

        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, params = builder.build_select_with_params(
            Injected.query().dimensions(Injected.country)
        )

        assert sql == (
            'SELECT "x\') FROM read_csv(\'/etc/passwd\') --" AS "country"\n'
            "FROM semantic_view('v', "
            "dimensions := ['x'') FROM read_csv(''/etc/passwd'') --'])"
        )
        assert params == []
        # The payload contributed no SQL of its own: strip the literals and the call is the
        # same shape it would be for a well-behaved field name. (The projection line holds
        # the name as a double-quoted identifier, which a single quote cannot leave.)
        assert outside_string_literals(from_line(sql)) == (
            "FROM semantic_view(<literal>, dimensions := [<literal>])"
        )

    def test_a_quote_in_a_view_name_cannot_open_a_new_clause(self):
        class Injected(SemanticView, view="v', dimensions := ['x'), (SELECT 1) --"):
            country = Dimension[str]()

        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(
            Injected.query().dimensions(Injected.country)
        )

        assert sql == (
            'SELECT "country" AS "country"\n'
            "FROM semantic_view('v'', dimensions := [''x''), (SELECT 1) --', "
            "dimensions := ['country'])"
        )
        assert outside_string_literals(sql) == (
            'SELECT "country" AS "country"\n'
            "FROM semantic_view(<literal>, dimensions := [<literal>])"
        )

    def test_a_quote_in_a_metric_name_is_doubled(self):
        class Injected(SemanticView, view="v"):
            revenue = Metric[int](source="o'brien")
            country = Dimension[str]()

        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(
            Injected.query().metrics(Injected.revenue).dimensions(Injected.country)
        )

        assert sql == (
            'SELECT "o\'brien" AS "revenue", "country" AS "country"\n'
            "FROM semantic_view('v', dimensions := ['country'], metrics := ['o''brien'])"
        )

    def test_a_quote_in_a_fact_name_is_doubled(self):
        class Injected(SemanticView, view="v"):
            unit_price = Fact[int](source="o'brien")

        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(
            Injected.query().dimensions(Injected.unit_price)
        )

        assert sql == (
            "SELECT \"o'brien\" AS \"unit_price\"\nFROM semantic_view('v', facts := ['o''brien'])"
        )

    def test_a_double_quote_in_a_projected_name_is_doubled(self):
        """The outer projection quotes each name as an identifier, so a ``"`` cannot end it."""

        class Injected(SemanticView, view="v"):
            country = Dimension[str](source="x\" FROM read_csv('/etc/passwd') --")

        builder = DuckDBSQLBuilder(DuckDBDialect())
        sql, _params = builder.build_select_with_params(
            Injected.query().dimensions(Injected.country)
        )

        assert sql.split("\n")[0] == ('SELECT "x"" FROM read_csv(\'/etc/passwd\') --" AS "country"')
