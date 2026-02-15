"""
Q-object filter composition for Cubano queries.

Q-objects encapsulate filter conditions and compose via boolean operators.
"""

from __future__ import annotations

from typing import Any


class Q:
    """
    Filter object for boolean query composition.

    Q objects encapsulate filter conditions and can be composed using
    boolean operators: & (AND), | (OR), ~ (NOT).

    WARNING: Python operator precedence applies - & binds tighter than |.
    Always use parentheses for clarity:
        (Q(a=1) | Q(b=2)) & Q(c=3)  <- GOOD
        Q(a=1) | Q(b=2) & Q(c=3)    <- CONFUSING (groups as a | (b & c))

    Examples:
        # Simple condition
        Q(country='US')

        # OR condition
        Q(country='US') | Q(country='CA')

        # AND condition
        Q(country='US') & Q(revenue__gt=1000)

        # NOT condition
        ~Q(country='US')

        # Complex nested
        (Q(country='US') | Q(country='CA')) & ~Q(revenue__lt=100)
    """

    # Connector types (class constants)
    AND: str = "AND"
    OR: str = "OR"

    def __init__(self, **kwargs: Any) -> None:
        """
        Create Q object from field=value keyword arguments.

        Args:
            **kwargs: Field conditions as keyword arguments
                     e.g., Q(country='US', revenue__gt=1000)
        """
        # Sort for consistent hashing/equality
        self.children: list[tuple[str, Any] | Q] = [*sorted(kwargs.items())]
        self.connector: str = self.AND
        self.negated: bool = False

    def _combine(self, other: object, conn: str) -> Q:
        """
        Combine two Q objects with specified connector.

        Args:
            other: Another Q object
            conn: Connector type (self.AND or self.OR)

        Returns:
            New Q object with both as children

        Raises:
            TypeError: If other is not a Q object
        """
        if not isinstance(other, Q):
            raise TypeError(
                f"Cannot combine Q with {type(other).__name__}. Both operands must be Q objects."
            )

        # Create new Q object with both as children
        obj = Q.__new__(Q)
        obj.children = [self, other]
        obj.connector = conn
        obj.negated = False
        return obj

    def __or__(self, other: object) -> Q:
        """Combine with OR: Q(a=1) | Q(b=2)."""
        return self._combine(other, self.OR)

    def __and__(self, other: object) -> Q:
        """Combine with AND: Q(a=1) & Q(b=2)."""
        return self._combine(other, self.AND)

    def __invert__(self) -> Q:
        """Negate with NOT: ~Q(a=1)."""
        obj = Q.__new__(Q)
        obj.children = [self]
        obj.connector = self.AND  # Connector doesn't matter for single child
        obj.negated = True
        return obj

    def __repr__(self) -> str:
        """Readable representation for debugging."""
        if self.children and isinstance(self.children[0], tuple):
            # Leaf node with conditions - all children are tuples
            # Type checker can't narrow list[T | U] based on first element,
            # so we cast for the iteration
            tuple_children: list[tuple[str, Any]] = self.children  # type: ignore[assignment]
            conditions = ", ".join(f"{k}={v!r}" for k, v in tuple_children)
            prefix = "~" if self.negated else ""
            return f"{prefix}Q({conditions})"
        else:
            # Branch node with child Q objects
            op = " | " if self.connector == self.OR else " & "
            children_repr = op.join(repr(c) for c in self.children)
            prefix = "~" if self.negated else ""
            return f"{prefix}({children_repr})"

    def __bool__(self) -> bool:
        """Return True if Q has children (useful for truthiness checks)."""
        return bool(self.children)
