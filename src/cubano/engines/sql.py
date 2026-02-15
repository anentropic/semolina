"""
SQL generation dialects for different backends.

Dialect classes encapsulate backend-specific SQL generation rules including
identifier quoting, metric wrapping, and SQL keyword variations. Each dialect
handles the syntactic differences between Snowflake, Databricks, and MockEngine.
"""

from abc import ABC, abstractmethod


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
