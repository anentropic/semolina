"""
MockPool for testing queries without a real warehouse connection.

MockPool provides the same connection interface as adbc-poolhouse pools
(pool.connect() context manager -> connection.cursor()), enabling
SemolinaCursor (Phase 26) and _Query.execute() to work identically
with both mock and real pools.
"""

from __future__ import annotations

import re
from typing import Any

from .engines.mock import _eval_predicate


class MockPool:
    """
    In-memory pool for testing without warehouse connections.

    Stores fixture data keyed by view name. Provides the same
    pool.connect() -> connection.cursor() interface that adbc-poolhouse
    pools expose, so downstream code works identically with mock and
    real pools.
    """

    def __init__(self) -> None:
        self._fixtures: dict[str, list[dict[str, Any]]] = {}

    def load(self, view_name: str, data: list[dict[str, Any]]) -> None:
        """
        Load fixture data for a semantic view.

        Args:
            view_name: View name matching SemanticView's view parameter.
            data: List of row dicts with field names as keys.
        """
        self._fixtures[view_name] = data

    def connect(self) -> MockConnection:
        """
        Return a mock connection (matches adbc-poolhouse pool.connect()).

        Returns:
            MockConnection wrapping this pool's fixtures.
        """
        return MockConnection(self._fixtures)

    def close(self) -> None:
        """No-op for mock (real pools release resources here)."""


class MockConnection:
    """In-memory connection wrapping fixture data."""

    def __init__(self, fixtures: dict[str, list[dict[str, Any]]]) -> None:
        self._fixtures = fixtures

    def cursor(self) -> MockCursor:
        """
        Return a MockCursor backed by this connection's fixtures.

        Returns:
            MockCursor instance.
        """
        return MockCursor(self._fixtures)

    def close(self) -> None:
        """No-op for mock connections."""

    def __enter__(self) -> MockConnection:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class MockCursor:
    """
    DBAPI 2.0-compatible cursor backed by in-memory fixture data.

    Receives _Query objects via _execute_query() for predicate evaluation.
    Returns results in DBAPI format: fetchall() returns list[tuple],
    description returns 7-element tuples.
    """

    def __init__(self, fixtures: dict[str, list[dict[str, Any]]]) -> None:
        self._fixtures = fixtures
        self._rows: list[tuple[Any, ...]] = []
        self._columns: list[str] = []
        self._description: list[tuple[Any, ...]] | None = None
        self._pos: int = 0

    @property
    def description(self) -> list[tuple[Any, ...]] | None:
        """
        DBAPI 2.0 description: list of 7-element tuples, or None before execute.

        Returns:
            List of (name, None, None, None, None, None, None) tuples after
            _execute_query, or None before any query has been executed.
        """
        return self._description

    @property
    def rowcount(self) -> int:
        """
        DBAPI 2.0 rowcount: number of rows from last execute.

        Returns:
            Number of rows in the current result set.
        """
        return len(self._rows)

    def execute(self, sql: str, params: Any = None) -> None:
        """
        DBAPI 2.0 execute -- populate results from fixture data.

        Extracts the view name from the SQL ``FROM`` clause and loads
        that view's fixture data. Does not parse predicates; returns
        all rows for the matched view.

        Args:
            sql: SQL string containing a FROM clause with the view name.
            params: Bind parameters (accepted for DBAPI compliance, unused).
        """
        match = re.search(r'FROM\s+"?(\w+)"?', sql, re.IGNORECASE)
        if match is None:
            self._rows = []
            self._columns = []
            self._description = []
            self._pos = 0
            return

        view_name = match.group(1)
        rows = self._fixtures.get(view_name, [])

        if rows:
            self._columns = list(rows[0].keys())
            self._rows = [tuple(row.get(col) for col in self._columns) for row in rows]
            self._description = [(col, None, None, None, None, None, None) for col in self._columns]
        else:
            self._rows = []
            self._columns = []
            self._description = []
        self._pos = 0

    def _execute_query(self, query: Any) -> None:
        """
        Execute query against fixtures using predicate evaluation.

        Extracts view_name from query fields (same pattern as MockEngine),
        filters fixture rows with _eval_predicate, and stores results in
        DBAPI 2.0 format.

        Args:
            query: _Query object with metrics, dimensions, and optional filters.
        """
        # Extract view_name from query fields (same pattern as MockEngine)
        view_name: str | None = None
        if query._metrics:
            owner = query._metrics[0].owner
            if owner is not None:
                view_name = owner._view_name
        elif query._dimensions:
            owner = query._dimensions[0].owner
            if owner is not None:
                view_name = owner._view_name

        if view_name is None:
            self._rows = []
            self._columns = []
            self._description = []
            return

        rows = self._fixtures.get(view_name, [])

        # Apply predicate filtering
        if query._filters is not None:
            rows = [r for r in rows if _eval_predicate(query._filters, r)]

        # Extract columns from first row (or from query fields if no rows)
        if rows:
            self._columns = list(rows[0].keys())
        else:
            # Derive columns from query metrics + dimensions
            cols: list[str] = []
            for m in query._metrics:
                if m.name is not None:
                    cols.append(m.name)
            for d in query._dimensions:
                if d.name is not None:
                    cols.append(d.name)
            self._columns = cols

        # Convert dict rows to tuples (DBAPI 2.0 format)
        self._rows = [tuple(row.get(col) for col in self._columns) for row in rows]

        # Build DBAPI description: 7-element tuples
        self._description = [(col, None, None, None, None, None, None) for col in self._columns]
        self._pos = 0

    def fetchall(self) -> list[tuple[Any, ...]]:
        """
        Fetch all remaining rows as list of tuples.

        Returns:
            List of tuple rows. Empty list if no rows remain.
        """
        result = self._rows[self._pos :]
        self._pos = len(self._rows)
        return result

    def fetchone(self) -> tuple[Any, ...] | None:
        """
        Fetch the next row, or None if exhausted.

        Returns:
            Single tuple row, or None if no rows remain.
        """
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchmany(self, size: int = 1) -> list[tuple[Any, ...]]:
        """
        Fetch up to size rows as tuples, advancing the cursor position.

        Args:
            size: Maximum number of rows to return. Defaults to 1.

        Returns:
            List of tuple rows (may be shorter than size).
        """
        result = self._rows[self._pos : self._pos + size]
        self._pos += len(result)
        return result

    def close(self) -> None:
        """No-op for mock cursors."""
