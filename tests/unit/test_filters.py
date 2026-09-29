"""
Tests for the predicate tree: how the operators compose it, and that it cannot change.

Construction and the class hierarchy are ``@dataclass`` behaviour and are not re-tested here.
What is Semolina's own: ``&``, ``|`` and ``~`` build the tree without simplifying it, and every
node is frozen, which is what lets a query holding a filter be hashed and compared (CORE-03).
How each node compiles to SQL is tested in ``test_sql.py``.
"""

import pytest

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
    StartsWith,
)

ALL_LOOKUPS = [
    Exact,
    NotEqual,
    Gt,
    Gte,
    Lt,
    Lte,
    In,
    Between,
    IsNull,
    Like,
    ILike,
    StartsWith,
    IStartsWith,
    EndsWith,
    IEndsWith,
    IExact,
]


class TestOperators:
    """``&``, ``|`` and ``~`` build nodes around the exact operands given."""

    def test_and_operator_returns_and(self) -> None:
        """``a & b`` is ``And(a, b)``, holding the operands themselves."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        result = a & b
        assert isinstance(result, And)
        assert result.left is a
        assert result.right is b

    def test_or_operator_returns_or(self) -> None:
        """``a | b`` is ``Or(a, b)``."""
        a = Exact("country", "US")
        b = Exact("country", "CA")
        result = a | b
        assert isinstance(result, Or)
        assert result.left is a
        assert result.right is b

    def test_invert_operator_returns_not(self) -> None:
        """``~a`` is ``Not(a)``."""
        a = Exact("country", "US")
        result = ~a
        assert isinstance(result, Not)
        assert result.inner is a


class TestCompositionChains:
    """Python's operator precedence decides the tree's shape; nothing is reassociated."""

    def test_and_then_or(self) -> None:
        """(a & b) | c produces Or(And(a, b), c)."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        c = Exact("region", "West")
        result = (a & b) | c
        assert isinstance(result, Or)
        assert isinstance(result.left, And)
        assert result.left.left is a
        assert result.left.right is b
        assert result.right is c

    def test_or_then_and(self) -> None:
        """(a | b) & c produces And(Or(a, b), c)."""
        a = Exact("country", "US")
        b = Exact("country", "CA")
        c = Gt("revenue", 1000)
        result = (a | b) & c
        assert isinstance(result, And)
        assert isinstance(result.left, Or)
        assert result.left.left is a
        assert result.left.right is b
        assert result.right is c

    def test_and_or_not_chain(self) -> None:
        """(a & b) | ~c produces Or(And(a, b), Not(c))."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        c = Exact("region", "West")
        result = (a & b) | ~c
        assert isinstance(result, Or)
        assert isinstance(result.left, And)
        assert isinstance(result.right, Not)
        assert result.right.inner is c


class TestNegationIsNotSimplified:
    """Repeated ``~`` nests rather than cancelling, so the SQL says what the code says."""

    def test_double_negation(self) -> None:
        """~~predicate produces Not(Not(predicate))."""
        a = Exact("country", "US")
        result = ~~a
        assert isinstance(result, Not)
        assert isinstance(result.inner, Not)
        assert result.inner.inner is a

    def test_triple_negation(self) -> None:
        """~~~predicate produces Not(Not(Not(predicate)))."""
        a = Exact("country", "US")
        result = ~~~a
        assert isinstance(result, Not)
        assert isinstance(result.inner, Not)
        assert isinstance(result.inner.inner, Not)
        assert result.inner.inner.inner is a


class TestNodesAreFrozen:
    """Every node refuses mutation, so a filter inside a query cannot change under it."""

    def test_and_is_frozen(self) -> None:
        """And cannot be modified."""
        node = And(left=Exact("a", 1), right=Gt("b", 2))
        with pytest.raises(AttributeError):
            node.left = Exact("c", 3)  # type: ignore[misc]

    def test_or_is_frozen(self) -> None:
        """Or cannot be modified."""
        node = Or(left=Exact("a", 1), right=Exact("b", 2))
        with pytest.raises(AttributeError):
            node.left = Exact("c", 3)  # type: ignore[misc]

    def test_not_is_frozen(self) -> None:
        """Not cannot be modified."""
        node = Not(inner=Exact("a", 1))
        with pytest.raises(AttributeError):
            node.inner = Exact("b", 2)  # type: ignore[misc]

    @pytest.mark.parametrize("cls", ALL_LOOKUPS)
    def test_lookup_frozen(self, cls: type[Lookup[object]]) -> None:
        """Every lookup subclass is frozen: neither its field nor its value can change."""
        node = cls("field", "value")
        with pytest.raises(AttributeError):
            node.field_name = "other"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            node.value = "other"  # type: ignore[misc]
