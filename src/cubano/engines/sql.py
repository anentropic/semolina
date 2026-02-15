"""
SQL generation dialects for different backends.

Dialect classes encapsulate backend-specific SQL generation rules including
identifier quoting, metric wrapping, and SQL keyword variations. Each dialect
handles the syntactic differences between Snowflake, Databricks, and MockEngine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Dialect(ABC):
    """
    Abstract base class for SQL generation dialects.

    Encapsulates backend-specific SQL generation rules. Each dialect defines
    how to quote identifiers (table and column names) and wrap metric fields
    for aggregation. SQL generators use Dialect instances to produce
    correct SQL for each backend without duplicating dialect logic.

    Identifier Quoting:
        - Identifiers are table names, column names, and aliases
        - String literals use single quotes ('text'), never quotes
        - Identifiers must be quoted to preserve case sensitivity and handle
          special characters or reserved keywords
        - Each dialect has one correct quoting character and escaping rule

    Metric Wrapping:
        - Metrics are wrapped differently depending on backend
        - Snowflake uses AGG(identifier) - metric aggregation function
        - Databricks uses MEASURE(identifier) - semantic metric reference
        - MockEngine uses AGG() for consistency with Snowflake

    Example:
        dialect = SnowflakeDialect()
        quoted = dialect.quote_identifier('my_column')  # Returns: "my_column"
        wrapped = dialect.wrap_metric('revenue')  # Returns: AGG("revenue")
    """

    @abstractmethod
    def quote_identifier(self, name: str) -> str:
        """
        Quote an identifier for use in SQL.

        Identifiers are table names, column names, schema names, and aliases.
        This method adds the appropriate quote character for the dialect and
        escapes any internal quotes to prevent SQL injection and syntax errors.

        Args:
            name: Unquoted identifier name (e.g., 'my_column', 'my_field')

        Returns:
            Quoted identifier safe for SQL (e.g., '"my_column"', '`my_field`')

        Note:
            - This method handles identifiers, not string literals
            - Single quotes (') are NEVER used for identifier quoting
            - Always escape internal quotes per dialect rules
            - Preserves case exactly as provided (not uppercased/lowercased)

        Example for Snowflake (double quotes, " escaped as ""):
            'my_field' -> '"my_field"'
            'field"with"quotes' -> '"field""with""quotes"'
            'REVENUE' -> '"REVENUE"'  # Preserves case

        Example for Databricks (backticks, ` escaped as ``):
            'my_field' -> '`my_field`'
            'field`with`ticks' -> '`field``with``ticks`'
        """
        pass

    @abstractmethod
    def wrap_metric(self, field_name: str) -> str:
        """
        Wrap a metric field for aggregation in SELECT clause.

        Metrics must be wrapped with backend-specific functions that signal
        to the database that this field is using semantic metric aggregation.
        This method returns the wrapped metric including proper identifier
        quoting.

        Args:
            field_name: Metric field name to wrap (e.g., 'revenue', 'cost')

        Returns:
            Wrapped metric with appropriate function (e.g., 'AGG("revenue")',
            'MEASURE(`cost`)')

        Note:
            - Snowflake requires AGG() for semantic metrics
            - Databricks requires MEASURE() for semantic metrics
            - MockEngine uses AGG() for Snowflake compatibility
            - The returned string includes proper identifier quoting

        Example:
            dialect = SnowflakeDialect()
            dialect.wrap_metric('revenue')  # Returns: AGG("revenue")

            dialect = DatabricksDialect()
            dialect.wrap_metric('revenue')  # Returns: MEASURE(`revenue`)
        """
        pass


class SnowflakeDialect(Dialect):
    """
    SQL dialect for Snowflake semantic views.

    Snowflake uses double quotes (") for identifier quoting and AGG() for
    metric aggregation. Internal quotes are escaped by doubling ("").

    Identifiers:
        - Unquoted identifiers are case-insensitive and stored as UPPERCASE
        - Quoted identifiers preserve case exactly
        - Always use this class to quote identifiers

    Metrics:
        - Wrapped with AGG() function defined in semantic view
        - AGG() only valid in queries against semantic views
    """

    def quote_identifier(self, name: str) -> str:
        """
        Quote identifier using double quotes with escaping.

        Internal double quotes are escaped by doubling them ("" -> "").
        This prevents SQL injection and handles identifiers with quotes.

        Args:
            name: Unquoted identifier

        Returns:
            Double-quoted identifier with internal " escaped as ""

        Example:
            'column' -> '"column"'
            'my"field' -> '"my""field"'
            'REVENUE' -> '"REVENUE"'
        """
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    def wrap_metric(self, field_name: str) -> str:
        """
        Wrap metric using AGG() function.

        Args:
            field_name: Metric field name

        Returns:
            AGG() wrapped metric with quoted identifier

        Example:
            'revenue' -> 'AGG("revenue")'
        """
        return f"AGG({self.quote_identifier(field_name)})"


class DatabricksDialect(Dialect):
    """
    SQL dialect for Databricks semantic views.

    Databricks uses backticks (`) for identifier quoting in standard mode and
    MEASURE() for metric aggregation. Internal backticks are escaped by
    doubling (`` -> ``).

    Identifiers:
        - Unquoted identifiers are case-insensitive and stored as lowercase
        - Backticks preserve case exactly
        - Always use this class to quote identifiers

    Metrics:
        - Wrapped with MEASURE() function defined in metric view
        - MEASURE() only valid in queries against metric views
        - Requires Databricks Runtime 12.2 LTS+
    """

    def quote_identifier(self, name: str) -> str:
        """
        Quote identifier using backticks with escaping.

        Internal backticks are escaped by doubling them (`` -> ``).
        This prevents SQL injection and handles identifiers with backticks.

        Args:
            name: Unquoted identifier

        Returns:
            Backtick-quoted identifier with internal ` escaped as ``

        Example:
            'column' -> '`column`'
            'my`field' -> '`my``field`'
            'REVENUE' -> '`REVENUE`'
        """
        escaped = name.replace("`", "``")
        return f"`{escaped}`"

    def wrap_metric(self, field_name: str) -> str:
        """
        Wrap metric using MEASURE() function.

        Args:
            field_name: Metric field name

        Returns:
            MEASURE() wrapped metric with quoted identifier

        Example:
            'revenue' -> 'MEASURE(`revenue`)'
        """
        return f"MEASURE({self.quote_identifier(field_name)})"


class MockDialect(Dialect):
    """
    SQL dialect for MockEngine testing.

    MockEngine uses Snowflake-compatible SQL syntax for consistency with
    the primary semantic view backend. Double quotes for identifier quoting
    and AGG() for metric wrapping.

    Identifiers:
        - Uses double quotes like Snowflake for consistency
        - Preserved case exactly (quoted identifiers)

    Metrics:
        - Wrapped with AGG() like Snowflake
        - MockEngine validates structure without executing real SQL
    """

    def quote_identifier(self, name: str) -> str:
        """
        Quote identifier using double quotes with escaping.

        Identical to SnowflakeDialect for consistency. Internal double quotes
        are escaped by doubling them ("" -> "").

        Args:
            name: Unquoted identifier

        Returns:
            Double-quoted identifier with internal " escaped as ""

        Example:
            'column' -> '"column"'
            'my"field' -> '"my""field"'
        """
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    def wrap_metric(self, field_name: str) -> str:
        """
        Wrap metric using AGG() function.

        Identical to SnowflakeDialect for consistency with Snowflake-like syntax.

        Args:
            field_name: Metric field name

        Returns:
            AGG() wrapped metric with quoted identifier

        Example:
            'revenue' -> 'AGG("revenue")'
        """
        return f"AGG({self.quote_identifier(field_name)})"


class SQLBuilder:
    """
    Composable SQL builder for generating dialect-specific SQL.

    Uses a Dialect instance for backend-specific identifier quoting and
    metric wrapping. Generates SQL by composing individual clauses
    (SELECT, FROM, WHERE, GROUP BY, ORDER BY, LIMIT) rather than using
    an AST approach. This keeps SQL generation simple and focused on
    known query structure.

    Attributes:
        dialect: Dialect instance for backend-specific SQL rules

    Example:
        from cubano import Query, SemanticView, Metric, Dimension
        from cubano.engines import SQLBuilder, MockDialect

        class Sales(SemanticView, view='sales_view'):
            revenue = Metric()
            country = Dimension()

        query = (Query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .limit(100))
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        # SELECT AGG("revenue"), "country"
        # FROM "sales_view"
        # GROUP BY ALL
        # LIMIT 100
    """

    def __init__(self, dialect: Dialect) -> None:
        """
        Initialize SQLBuilder with a dialect.

        Args:
            dialect: Dialect instance for backend-specific SQL generation
        """
        self.dialect = dialect

    def build_select(self, query: Any) -> str:  # type: ignore[name-defined]
        r"""
        Build a complete SELECT statement from a Query object.

        Orchestrates SQL generation by composing individual clauses
        (SELECT, FROM, WHERE, GROUP BY, ORDER BY, LIMIT). Each clause
        is built separately and joined with newlines.

        Args:
            query: Query object to convert to SQL

        Returns:
            Formatted SQL string with each clause on a new line

        Example:
            query = Query().metrics(Sales.revenue).dimensions(Sales.country)
            sql = builder.build_select(query)
            # Returns: "SELECT AGG("revenue"), "country"\nFROM "sales_view"..."
        """
        parts: list[str] = []

        # Build main clauses
        parts.append(self._build_select_clause(query))
        parts.append(self._build_from_clause(query))

        # Optional clauses
        if query._filters is not None:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_where_clause(query))

        if query._dimensions:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_group_by_clause(query))

        if query._order_by_fields:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_order_by_clause(query))

        if query._limit_value is not None:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_limit_clause(query))

        return "\n".join(parts)

    def _build_select_clause(self, query: Any) -> str:
        """
        Build the SELECT clause with metrics and dimensions.

        Metrics are wrapped using the dialect's wrap_metric() method
        (e.g., AGG("revenue") for Snowflake). Dimensions and facts are
        quoted using the dialect's quote_identifier() method
        (e.g., "country" for Snowflake).

        Args:
            query: Query object with metrics and dimensions

        Returns:
            SELECT clause (e.g., 'SELECT AGG("revenue"), "country"')
        """
        select_items: list[str] = []

        # Add metrics (wrapped in AGG() or MEASURE())
        for metric in query._metrics:  # type: ignore[reportPrivateUsage]
            assert metric.name is not None
            wrapped = self.dialect.wrap_metric(metric.name)
            select_items.append(wrapped)

        # Add dimensions and facts (quoted identifiers)
        for dim in query._dimensions:  # type: ignore[reportPrivateUsage]
            assert dim.name is not None
            quoted = self.dialect.quote_identifier(dim.name)
            select_items.append(quoted)

        return "SELECT " + ", ".join(select_items)

    def _build_from_clause(self, query: Any) -> str:
        """
        Build the FROM clause using the view name from query fields.

        Extracts the view name from the first field's owner model
        (either from metrics or dimensions). Uses the dialect's
        quote_identifier() method to quote the view name.

        Args:
            query: Query object with metrics or dimensions

        Returns:
            FROM clause (e.g., 'FROM "sales_view"')
        """
        # Get view name from first field's owner
        view_name: str | None = None

        if query._metrics:  # type: ignore[reportPrivateUsage]
            owner = query._metrics[0].owner  # type: ignore[reportPrivateUsage]
            assert owner is not None
            view_name = owner._view_name  # type: ignore[reportPrivateUsage]

        elif query._dimensions:  # type: ignore[reportPrivateUsage]
            owner = query._dimensions[0].owner  # type: ignore[reportPrivateUsage]
            assert owner is not None
            view_name = owner._view_name  # type: ignore[reportPrivateUsage]

        assert view_name is not None, "View name not found on field owner"

        quoted_view = self.dialect.quote_identifier(view_name)
        return f"FROM {quoted_view}"

    def _build_where_clause(self, query: Any) -> str:
        """
        Build the WHERE clause from query filters.

        Converts query._filters (Q object) to WHERE clause. For now,
        returns a placeholder since full Q-object rendering to SQL is
        complex and deferred to Phase 4 (where filter execution happens).

        Args:
            query: Query object with filters

        Returns:
            WHERE clause (e.g., 'WHERE 1=1' as placeholder)

        Note:
            Q-object to SQL translation requires a separate query filter
            compiler. This is implemented in Phase 4.
        """
        # Placeholder: For Phase 3, we just show structure
        # Full Q-object rendering happens in Phase 4
        return "WHERE 1=1"

    def _build_group_by_clause(self, query: Any) -> str:
        """
        Build the GROUP BY clause using GROUP BY ALL.

        Both Snowflake and Databricks support GROUP BY ALL, which
        automatically groups by all non-aggregated SELECT columns.
        This is simpler and more maintainable than manually listing
        each dimension field.

        Args:
            query: Query object with dimensions

        Returns:
            GROUP BY clause (e.g., 'GROUP BY ALL')

        Note:
            GROUP BY ALL requires:
            - Snowflake: No version constraint
            - Databricks: Runtime 12.2 LTS+
        """
        return "GROUP BY ALL"

    def _build_order_by_clause(self, query: Any) -> str:
        """
        Build the ORDER BY clause from query order_by_fields.

        Handles both bare Field instances (sorted ascending by default)
        and OrderTerm instances (with explicit direction and NULLS
        handling). Uses the dialect's quote_identifier() method to quote
        field names.

        Args:
            query: Query object with order_by_fields

        Returns:
            ORDER BY clause (e.g., 'ORDER BY "revenue" DESC NULLS FIRST')
        """
        from cubano.fields import OrderTerm

        order_items: list[str] = []

        for field_spec in query._order_by_fields:  # type: ignore[reportPrivateUsage]
            # Handle OrderTerm (from field.asc() or field.desc())
            if isinstance(field_spec, OrderTerm):
                field = field_spec.field
                assert field.name is not None
                quoted_field = self.dialect.quote_identifier(field.name)

                # Add direction
                direction = "DESC" if field_spec.descending else "ASC"
                order_item = f"{quoted_field} {direction}"

                # Add NULLS clause if specified
                if field_spec.nulls.value is not None:  # Check if not DEFAULT
                    nulls_clause = field_spec.nulls.value
                    order_item += f" NULLS {nulls_clause}"

                order_items.append(order_item)

            # Handle bare Field (defaults to ascending)
            else:
                assert field_spec.name is not None
                quoted_field = self.dialect.quote_identifier(field_spec.name)
                order_items.append(f"{quoted_field} ASC")

        return "ORDER BY " + ", ".join(order_items)

    def _build_limit_clause(self, query: Any) -> str:
        """
        Build the LIMIT clause from query limit value.

        Args:
            query: Query object with limit_value set

        Returns:
            LIMIT clause (e.g., 'LIMIT 100')
        """
        return f"LIMIT {query._limit_value}"  # type: ignore[reportPrivateUsage]
