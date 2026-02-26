"""
Tests for predicate tree IR: Predicate, And, Or, Not, Lookup[T], and core lookups.

Tests cover predicate construction, boolean operators (&, |, ~), frozen immutability,
isinstance hierarchy, composition chains, and edge cases.
"""

import pytest

from cubano.filters import (
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


class TestPredicateBaseClass:
    """Test Predicate base class is plain class with operator methods."""

    def test_predicate_is_not_dataclass(self) -> None:
        """Predicate base is a plain class, not a dataclass."""
        import dataclasses

        assert not dataclasses.is_dataclass(Predicate)

    def test_predicate_instantiation(self) -> None:
        """Predicate can be instantiated (it's a plain class)."""
        p = Predicate()
        assert isinstance(p, Predicate)

    def test_and_operator_returns_and(self) -> None:
        """Predicate.__and__ returns And node."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        result = a & b
        assert isinstance(result, And)
        assert result.left is a
        assert result.right is b

    def test_or_operator_returns_or(self) -> None:
        """Predicate.__or__ returns Or node."""
        a = Exact("country", "US")
        b = Exact("country", "CA")
        result = a | b
        assert isinstance(result, Or)
        assert result.left is a
        assert result.right is b

    def test_invert_operator_returns_not(self) -> None:
        """Predicate.__invert__ returns Not node."""
        a = Exact("country", "US")
        result = ~a
        assert isinstance(result, Not)
        assert result.inner is a


class TestAndNode:
    """Test And composite node."""

    def test_and_construction(self) -> None:
        """And(left, right) stores both predicates."""
        left = Exact("a", 1)
        right = Gt("b", 2)
        node = And(left=left, right=right)
        assert node.left is left
        assert node.right is right

    def test_and_is_predicate(self) -> None:
        """And is a Predicate subclass."""
        node = And(left=Exact("a", 1), right=Gt("b", 2))
        assert isinstance(node, Predicate)

    def test_and_is_frozen(self) -> None:
        """And is a frozen dataclass -- cannot modify attributes."""
        node = And(left=Exact("a", 1), right=Gt("b", 2))
        with pytest.raises(AttributeError):
            node.left = Exact("c", 3)  # type: ignore[misc]

    def test_and_is_dataclass(self) -> None:
        """And is a frozen dataclass."""
        import dataclasses

        assert dataclasses.is_dataclass(And)


class TestOrNode:
    """Test Or composite node."""

    def test_or_construction(self) -> None:
        """Or(left, right) stores both predicates."""
        left = Exact("a", 1)
        right = Exact("b", 2)
        node = Or(left=left, right=right)
        assert node.left is left
        assert node.right is right

    def test_or_is_predicate(self) -> None:
        """Or is a Predicate subclass."""
        node = Or(left=Exact("a", 1), right=Exact("b", 2))
        assert isinstance(node, Predicate)

    def test_or_is_frozen(self) -> None:
        """Or is a frozen dataclass -- cannot modify attributes."""
        node = Or(left=Exact("a", 1), right=Exact("b", 2))
        with pytest.raises(AttributeError):
            node.left = Exact("c", 3)  # type: ignore[misc]


class TestNotNode:
    """Test Not composite node."""

    def test_not_construction(self) -> None:
        """Not(inner) stores the negated predicate."""
        inner = Exact("a", 1)
        node = Not(inner=inner)
        assert node.inner is inner

    def test_not_is_predicate(self) -> None:
        """Not is a Predicate subclass."""
        node = Not(inner=Exact("a", 1))
        assert isinstance(node, Predicate)

    def test_not_is_frozen(self) -> None:
        """Not is a frozen dataclass -- cannot modify attributes."""
        node = Not(inner=Exact("a", 1))
        with pytest.raises(AttributeError):
            node.inner = Exact("b", 2)  # type: ignore[misc]


class TestLookupBase:
    """Test Lookup[T] generic leaf base class."""

    def test_lookup_construction(self) -> None:
        """Lookup(field_name, value) stores both attributes."""
        node = Lookup(field_name="country", value="US")
        assert node.field_name == "country"
        assert node.value == "US"

    def test_lookup_is_predicate(self) -> None:
        """Lookup is a Predicate subclass."""
        node = Lookup(field_name="x", value=1)
        assert isinstance(node, Predicate)

    def test_lookup_is_frozen(self) -> None:
        """Lookup is a frozen dataclass -- cannot modify attributes."""
        node = Lookup(field_name="x", value=1)
        with pytest.raises(AttributeError):
            node.field_name = "y"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            node.value = 2  # type: ignore[misc]


class TestCoreLookupSubclasses:
    """Test all 16 core lookup subclasses instantiate correctly."""

    def test_exact(self) -> None:
        """Exact("country", "US") creates lookup node."""
        node = Exact("country", "US")
        assert node.field_name == "country"
        assert node.value == "US"
        assert isinstance(node, Lookup)
        assert isinstance(node, Predicate)

    def test_not_equal(self) -> None:
        """NotEqual("country", "US") creates lookup node."""
        node = NotEqual("country", "US")
        assert node.field_name == "country"
        assert node.value == "US"
        assert isinstance(node, Lookup)
        assert isinstance(node, Predicate)

    def test_gt(self) -> None:
        """Gt("revenue", 1000) creates lookup node."""
        node = Gt("revenue", 1000)
        assert node.field_name == "revenue"
        assert node.value == 1000

    def test_gte(self) -> None:
        """Gte("revenue", 1000) creates lookup node."""
        node = Gte("revenue", 1000)
        assert node.field_name == "revenue"
        assert node.value == 1000

    def test_lt(self) -> None:
        """Lt("revenue", 100) creates lookup node."""
        node = Lt("revenue", 100)
        assert node.field_name == "revenue"
        assert node.value == 100

    def test_lte(self) -> None:
        """Lte("revenue", 100) creates lookup node."""
        node = Lte("revenue", 100)
        assert node.field_name == "revenue"
        assert node.value == 100

    def test_in(self) -> None:
        """In("country", ["US", "CA"]) creates lookup node."""
        node = In("country", ["US", "CA"])
        assert node.field_name == "country"
        assert node.value == ["US", "CA"]

    def test_between(self) -> None:
        """Between("date", (start, end)) creates lookup node."""
        node = Between("date", ("2025-01-01", "2025-12-31"))
        assert node.field_name == "date"
        assert node.value == ("2025-01-01", "2025-12-31")

    def test_is_null(self) -> None:
        """IsNull("region", True) creates lookup node."""
        node = IsNull("region", True)
        assert node.field_name == "region"
        assert node.value is True

    def test_like(self) -> None:
        """Like("name", "%widget%") creates lookup node."""
        node = Like("name", "%widget%")
        assert node.field_name == "name"
        assert node.value == "%widget%"

    def test_ilike(self) -> None:
        """ILike("name", "%Widget%") creates lookup node."""
        node = ILike("name", "%Widget%")
        assert node.field_name == "name"
        assert node.value == "%Widget%"

    def test_starts_with(self) -> None:
        """StartsWith("name", "wid") creates lookup node."""
        node = StartsWith("name", "wid")
        assert node.field_name == "name"
        assert node.value == "wid"

    def test_istarts_with(self) -> None:
        """IStartsWith("name", "Wid") creates lookup node."""
        node = IStartsWith("name", "Wid")
        assert node.field_name == "name"
        assert node.value == "Wid"

    def test_ends_with(self) -> None:
        """EndsWith("name", "get") creates lookup node."""
        node = EndsWith("name", "get")
        assert node.field_name == "name"
        assert node.value == "get"

    def test_iends_with(self) -> None:
        """IEndsWith("name", "Get") creates lookup node."""
        node = IEndsWith("name", "Get")
        assert node.field_name == "name"
        assert node.value == "Get"

    def test_iexact(self) -> None:
        """IExact("country", "us") creates lookup node."""
        node = IExact("country", "us")
        assert node.field_name == "country"
        assert node.value == "us"


class TestAllLookupsArePredicate:
    """All 16 lookup subclasses are Predicate instances."""

    @pytest.mark.parametrize(
        "cls",
        [
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
        ],
    )
    def test_lookup_isinstance_predicate(self, cls: type[Lookup[object]]) -> None:
        """Every lookup subclass instance is a Predicate."""
        node = cls("field", "value")
        assert isinstance(node, Predicate)
        assert isinstance(node, Lookup)


class TestAllLookupsAreFrozen:
    """All 16 lookup subclasses enforce frozen immutability."""

    @pytest.mark.parametrize(
        "cls",
        [
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
        ],
    )
    def test_lookup_frozen(self, cls: type[Lookup[object]]) -> None:
        """Every lookup subclass is frozen -- cannot modify attributes."""
        node = cls("field", "value")
        with pytest.raises(AttributeError):
            node.field_name = "other"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            node.value = "other"  # type: ignore[misc]


class TestCompositionChains:
    """Test complex predicate composition chains."""

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

    def test_composition_creates_new_nodes(self) -> None:
        """Composition always creates new nodes, never mutates existing ones."""
        a = Exact("country", "US")
        b = Gt("revenue", 1000)
        _ = a & b
        _ = a | b
        _ = ~a
        # Original nodes unchanged -- they're frozen so this is guaranteed
        assert a.field_name == "country"
        assert a.value == "US"
        assert b.field_name == "revenue"
        assert b.value == 1000


class TestDoubleNegation:
    """Test nested NOT (double negation) edge case."""

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


class TestEdgeCases:
    """Test edge cases for predicate construction."""

    def test_empty_in_is_valid(self) -> None:
        """In("field", []) is valid construction (compiler handles semantics)."""
        node = In("field", [])
        assert node.field_name == "field"
        assert node.value == []

    def test_is_null_false(self) -> None:
        """IsNull("field", False) is valid (IS NOT NULL semantics)."""
        node = IsNull("field", False)
        assert node.value is False

    def test_between_with_tuples(self) -> None:
        """Between with tuple value preserves both bounds."""
        node = Between("date", (10, 20))
        lo, hi = node.value
        assert lo == 10
        assert hi == 20
