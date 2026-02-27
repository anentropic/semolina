"""
SQL generation dialects for different backends.

Dialect classes encapsulate backend-specific SQL generation rules including
identifier quoting, metric wrapping, placeholder styles, and SQL keyword
variations. Each dialect handles the syntactic differences between Snowflake,
Databricks, and MockEngine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, cast

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
    Not,
    NotEqual,
    Or,
    Predicate,
    StartsWith,
)


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

    @property
    @abstractmethod
    def placeholder(self) -> str:
        """
        Parameterized query placeholder for this dialect.

        Returns the placeholder string used in parameterized SQL queries.
        Each dialect uses its database driver's native placeholder format.

        Returns:
            Placeholder string (e.g., '%s' for Snowflake/Mock, '?' for Databricks)
        """
        ...

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

    @abstractmethod
    def normalize_identifier(self, name: str) -> str:
        """
        Fold a Python field name to the SQL column name the warehouse stores.

        Called when field.source is None. Each dialect knows its default
        identifier folding: Snowflake stores unquoted identifiers as UPPERCASE;
        Databricks as lowercase; Mock passes through unchanged.

        Args:
            name: Python field name (e.g., 'order_id', 'revenue')

        Returns:
            SQL column name as stored in the warehouse (e.g., 'ORDER_ID' for
            Snowflake, 'order_id' for Databricks, 'order_id' for Mock)
        """
        ...


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

    @property
    def placeholder(self) -> str:
        """Return %s placeholder for snowflake-connector-python."""
        return "%s"

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

    def normalize_identifier(self, name: str) -> str:
        """
        Fold Python field name to Snowflake SQL column name.

        Snowflake stores unquoted identifiers as UPPERCASE.

        Args:
            name: Python field name

        Returns:
            Uppercase SQL column name
        """
        return name.upper()


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

    @property
    def placeholder(self) -> str:
        """Return ? placeholder for databricks-sql-connector."""
        return "?"

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

    def normalize_identifier(self, name: str) -> str:
        """
        Fold Python field name to Databricks SQL column name.

        Databricks stores unquoted identifiers as lowercase.

        Args:
            name: Python field name

        Returns:
            Lowercase SQL column name
        """
        return name.lower()


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

    @property
    def placeholder(self) -> str:
        """Return %s placeholder (Snowflake-compatible)."""
        return "%s"

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

    def normalize_identifier(self, name: str) -> str:
        """
        Pass through identifier unchanged (identity transform).

        MockDialect does not apply any case folding, preserving the Python
        field name as-is. This means existing test assertions remain unchanged
        since MockDialect is identity for normalize_identifier.

        Args:
            name: Python field name

        Returns:
            Unchanged name
        """
        return name


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
        ```python
        from semolina import SemanticView, Metric, Dimension
        from semolina.engines import SQLBuilder, MockDialect


        class Sales(SemanticView, view="sales_view"):
            revenue = Metric()
            country = Dimension()


        query = (
            Sales.query()
            .metrics(Sales.revenue)
            .dimensions(Sales.country)
            .limit(100)
        )
        builder = SQLBuilder(MockDialect())
        sql = builder.build_select(query)
        # SELECT AGG("revenue"), "country"
        # FROM "sales_view"
        # GROUP BY ALL
        # LIMIT 100
        ```
    """

    def __init__(self, dialect: Dialect) -> None:
        """
        Initialize SQLBuilder with a dialect.

        Args:
            dialect: Dialect instance for backend-specific SQL generation
        """
        self.dialect = dialect

    def _resolve_col_name(self, field: Any) -> str:
        """
        Resolve the SQL-facing column name for a field.

        If the field has an explicit ``source`` set, that takes priority
        (used verbatim). Otherwise, the dialect's ``normalize_identifier``
        is called to fold the Python field name to the warehouse's storage
        convention (e.g., UPPERCASE for Snowflake, lowercase for Databricks).

        Args:
            field: Field descriptor with ``name`` and ``source`` attributes.

        Returns:
            SQL column name to use in generated SQL.
        """
        assert field.name is not None
        if field.source is not None:
            return field.source  # type: ignore[no-any-return]
        return self.dialect.normalize_identifier(field.name)

    def _compile_predicate(self, node: Predicate) -> tuple[str, list[Any]]:
        """
        Compile a Predicate tree into a SQL fragment with bind parameters.

        Pattern-matches on the predicate node type and emits the appropriate
        SQL fragment and parameter list. Uses ``self.dialect.placeholder``
        for parameterized placeholders (never hardcoded).

        Args:
            node: A Predicate tree node (leaf Lookup, or composite And/Or/Not)

        Returns:
            Tuple of (sql_fragment, params_list)

        Raises:
            NotImplementedError: For unknown Lookup subclasses
            TypeError: For non-Predicate input
        """
        ph = self.dialect.placeholder
        q = self.dialect.quote_identifier

        match node:
            # -- Composite nodes -------------------------------------------
            case And(left=left, right=right):
                l_sql, l_params = self._compile_predicate(left)
                r_sql, r_params = self._compile_predicate(right)
                return f"({l_sql} AND {r_sql})", l_params + r_params

            case Or(left=left, right=right):
                l_sql, l_params = self._compile_predicate(left)
                r_sql, r_params = self._compile_predicate(right)
                return f"({l_sql} OR {r_sql})", l_params + r_params

            case Not(inner=inner):
                i_sql, i_params = self._compile_predicate(inner)
                return f"NOT ({i_sql})", i_params

            # -- Leaf lookups (order matters: specific before generic) ------
            # Predicates store Python field_name strings AND optional source= override.
            # Column resolution mirrors _resolve_col_name: use source verbatim when set,
            # otherwise apply dialect.normalize_identifier.
            case Exact(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} = {ph}", [v]

            case NotEqual(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} != {ph}", [v]

            case Gt(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} > {ph}", [v]

            case Gte(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} >= {ph}", [v]

            case Lt(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} < {ph}", [v]

            case Lte(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} <= {ph}", [v]

            case In(field_name=f, value=v):
                if not v:
                    return "1 = 0", []
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                placeholders = ", ".join(ph for _ in v)
                return f"{q(nf)} IN ({placeholders})", list(v)

            case Between(field_name=f, value=v):
                lo, hi = v
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} BETWEEN {ph} AND {ph}", [lo, hi]

            case IsNull(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                if v:
                    return f"{q(nf)} IS NULL", []
                return f"{q(nf)} IS NOT NULL", []

            # v0.2: Do NOT escape % and _ in user values before appending
            # the wildcard. The LIKE escaping question is deferred to v0.3.
            case StartsWith(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} LIKE {ph}", [v + "%"]

            case IStartsWith(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} ILIKE {ph}", [v + "%"]

            case EndsWith(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} LIKE {ph}", ["%" + v]

            case IEndsWith(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} ILIKE {ph}", ["%" + v]

            case Like(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} LIKE {ph}", [v]

            case ILike(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} ILIKE {ph}", [v]

            case IExact(field_name=f, value=v):
                nf = (
                    node.source if node.source is not None else self.dialect.normalize_identifier(f)
                )
                return f"{q(nf)} ILIKE {ph}", [v]

            # -- Catch-all: unknown Lookup subclass or non-Predicate ---------
            case _:
                # Cast through object to avoid reportUnknownMemberType
                # on Lookup[Unknown] from the match narrowing
                cls_name = type(cast("object", node)).__name__
                if isinstance(node, Lookup):
                    msg = (
                        f"Unsupported lookup type: {cls_name}. "
                        f"Add a case for it in _compile_predicate()."
                    )
                    raise NotImplementedError(msg)
                msg = (
                    f"Expected Predicate, got {cls_name}. "
                    f"Use Lookup subclasses or And/Or/Not composites."
                )
                raise TypeError(msg)

    def _build_where_clause_with_params(self, query: Any) -> tuple[str, list[Any]]:
        """
        Build WHERE clause with parameterized bind values.

        Args:
            query: Query object with _filters set

        Returns:
            Tuple of ("WHERE {sql}", params_list)
        """
        sql, params = self._compile_predicate(query._filters)  # type: ignore[reportPrivateUsage]
        return f"WHERE {sql}", params

    def build_select_with_params(self, query: Any) -> tuple[str, list[Any]]:
        """
        Build a complete SELECT statement with parameterized bind values.

        Same as build_select() but returns (sql_template, params) for
        execution via cursor.execute(sql, params).

        Args:
            query: Query object to convert to SQL

        Returns:
            Tuple of (sql_template, params_list). The sql_template contains
            dialect-specific placeholders (%s or ?) instead of literal values.
        """
        parts: list[str] = []
        all_params: list[Any] = []

        # Build main clauses
        parts.append(self._build_select_clause(query))
        parts.append(self._build_from_clause(query))

        # Optional clauses
        if query._filters is not None:  # type: ignore[reportPrivateUsage]
            where_sql, where_params = self._build_where_clause_with_params(query)
            parts.append(where_sql)
            all_params.extend(where_params)

        if query._dimensions:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_group_by_clause(query))

        if query._order_by_fields:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_order_by_clause(query))

        if query._limit_value is not None:  # type: ignore[reportPrivateUsage]
            parts.append(self._build_limit_clause(query))

        return "\n".join(parts), all_params

    def render_inline(self, sql_template: str, params: list[Any]) -> str:
        """
        Replace placeholders with repr(param) for display/debugging.

        Substitutes each placeholder in the SQL template with the repr() of
        the corresponding parameter, one at a time (left to right). This is
        for human-readable output only -- never for execution.

        Args:
            sql_template: SQL string with placeholders (%s or ?)
            params: List of parameter values

        Returns:
            SQL string with literal values substituted in
        """
        result = sql_template
        ph = self.dialect.placeholder
        for param in params:
            result = result.replace(ph, repr(param), 1)
        return result

    def build_select(self, query: Any) -> str:  # type: ignore[name-defined]
        r"""
        Build a complete SELECT statement from a _Query object.

        Orchestrates SQL generation by composing individual clauses
        (SELECT, FROM, WHERE, GROUP BY, ORDER BY, LIMIT). Each clause
        is built separately and joined with newlines.

        For parameterized output, use build_select_with_params() instead.
        This method calls build_select_with_params() then render_inline()
        for backward-compatible inline-rendered SQL.

        Args:
            query: Query object to convert to SQL

        Returns:
            Formatted SQL string with each clause on a new line,
            values rendered inline via repr()

        Example:
            ```python
            query = (
                Sales.query()
                .metrics(Sales.revenue)
                .dimensions(Sales.country)
            )
            sql = builder.build_select(query)
            # Returns: "SELECT AGG("revenue"), "country"\nFROM "sales_view"..."
            ```
        """
        sql_template, params = self.build_select_with_params(query)
        return self.render_inline(sql_template, params)

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
            col_name = self._resolve_col_name(metric)
            wrapped = self.dialect.wrap_metric(col_name)
            select_items.append(wrapped)

        # Add dimensions and facts (quoted identifiers)
        for dim in query._dimensions:  # type: ignore[reportPrivateUsage]
            col_name = self._resolve_col_name(dim)
            quoted = self.dialect.quote_identifier(col_name)
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
        Build the WHERE clause from query filters (inline-rendered).

        Compiles query._filters (Predicate tree) to a WHERE clause with
        values rendered inline via repr() for human-readable output.
        For parameterized output, use _build_where_clause_with_params().

        Args:
            query: Query object with filters

        Returns:
            WHERE clause with inline-rendered values
        """
        where_sql, params = self._build_where_clause_with_params(query)
        return self.render_inline(where_sql, params)

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
        handling). Metric fields are wrapped using the dialect's
        wrap_metric() method; other fields use quote_identifier().

        Args:
            query: Query object with order_by_fields

        Returns:
            ORDER BY clause (e.g., 'ORDER BY "revenue" DESC NULLS FIRST')
        """
        from semolina.fields import Metric, OrderTerm

        def _quote_field(field: Any) -> str:
            col_name = self._resolve_col_name(field)
            if isinstance(field, Metric):
                return self.dialect.wrap_metric(col_name)
            return self.dialect.quote_identifier(col_name)

        order_items: list[str] = []

        for field_spec in query._order_by_fields:  # type: ignore[reportPrivateUsage]
            # Handle OrderTerm (from field.asc() or field.desc())
            if isinstance(field_spec, OrderTerm):
                field = field_spec.field
                quoted_field = _quote_field(field)

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
                order_items.append(f"{_quote_field(field_spec)} ASC")

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
