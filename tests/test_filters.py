"""
Tests for Q-object filter composition.

Tests cover Q-object creation, boolean operators (&, |, ~), tree structure,
type validation, and repr output.
"""

import pytest

from cubano.filters import Q


class TestQObjectCreation:
    """Test basic Q-object creation from keyword arguments."""

    def test_empty_q_object(self) -> None:
        """Q() with no kwargs creates empty leaf node."""
        q = Q()
        assert q.children == []
        assert q.connector == Q.AND
        assert q.negated is False

    def test_single_condition(self) -> None:
        """Q(country='US') creates leaf with one condition."""
        q = Q(country="US")
        assert q.children == [("country", "US")]
        assert q.connector == Q.AND
        assert q.negated is False

    def test_multiple_conditions(self) -> None:
        """Q(a=1, b=2) creates leaf with multiple conditions sorted."""
        q = Q(country="US", region="West")
        # Children should be sorted for consistent ordering
        assert len(q.children) == 2
        assert ("country", "US") in q.children
        assert ("region", "West") in q.children
        assert q.connector == Q.AND
        assert q.negated is False

    def test_children_sorted(self) -> None:
        """Children are sorted for consistent hashing/equality."""
        q1 = Q(b=2, a=1)
        q2 = Q(a=1, b=2)
        # Both should have same sorted children
        assert q1.children == q2.children
        assert q1.children == [("a", 1), ("b", 2)]


class TestQObjectOrOperator:
    """Test Q-object OR composition with | operator."""

    def test_simple_or(self) -> None:
        """Q(a=1) | Q(b=2) creates OR-connected tree."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        result = q1 | q2

        assert result.connector == Q.OR
        assert result.children == [q1, q2]
        assert result.negated is False

    def test_or_preserves_operands(self) -> None:
        """Original Q objects unchanged after OR composition."""
        q1 = Q(country="US")
        q2 = Q(country="CA")
        original_q1_children = q1.children
        original_q2_children = q2.children

        result = q1 | q2

        # Originals unchanged
        assert q1.children == original_q1_children
        assert q2.children == original_q2_children
        # Result has both as children
        assert result.children == [q1, q2]

    def test_or_with_non_q_raises_type_error(self) -> None:
        """Q(a=1) | 'not a Q' raises TypeError."""
        q = Q(a=1)
        with pytest.raises(TypeError, match="Cannot combine Q with"):
            q | "not a Q"  # type: ignore

    def test_or_with_int_raises_type_error(self) -> None:
        """Q(a=1) | 42 raises TypeError."""
        q = Q(a=1)
        with pytest.raises(TypeError, match="Cannot combine Q with"):
            q | 42  # type: ignore


class TestQObjectAndOperator:
    """Test Q-object AND composition with & operator."""

    def test_simple_and(self) -> None:
        """Q(a=1) & Q(b=2) creates AND-connected tree."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        result = q1 & q2

        assert result.connector == Q.AND
        assert result.children == [q1, q2]
        assert result.negated is False

    def test_and_preserves_operands(self) -> None:
        """Original Q objects unchanged after AND composition."""
        q1 = Q(country="US")
        q2 = Q(revenue__gt=1000)
        original_q1_children = q1.children
        original_q2_children = q2.children

        result = q1 & q2

        # Originals unchanged
        assert q1.children == original_q1_children
        assert q2.children == original_q2_children
        # Result has both as children
        assert result.children == [q1, q2]

    def test_and_with_non_q_raises_type_error(self) -> None:
        """Q(a=1) & 'not a Q' raises TypeError."""
        q = Q(a=1)
        with pytest.raises(TypeError, match="Cannot combine Q with"):
            q & "not a Q"  # type: ignore

    def test_and_with_dict_raises_type_error(self) -> None:
        """Q(a=1) & {'b': 2} raises TypeError."""
        q = Q(a=1)
        with pytest.raises(TypeError, match="Cannot combine Q with"):
            q & {"b": 2}  # type: ignore


class TestQObjectInvertOperator:
    """Test Q-object NOT composition with ~ operator."""

    def test_simple_invert(self) -> None:
        """~Q(a=1) creates negated Q-object."""
        q = Q(a=1)
        result = ~q

        assert result.negated is True
        assert result.children == [q]
        # Original unchanged
        assert q.negated is False

    def test_double_invert(self) -> None:
        """~~Q(a=1) creates double-negated Q-object."""
        q = Q(a=1)
        result = ~~q

        # Each invert wraps in a new Q
        assert result.negated is True
        assert len(result.children) == 1
        inner = result.children[0]
        assert isinstance(inner, Q)
        assert inner.negated is True
        assert inner.children == [q]

    def test_invert_preserves_original(self) -> None:
        """Original Q unchanged after inversion."""
        q = Q(country="US")
        original_negated = q.negated
        original_children = q.children

        result = ~q

        assert q.negated == original_negated
        assert q.children == original_children
        assert result.negated is True


class TestQObjectNestedComposition:
    """Test complex nested Q-object compositions."""

    def test_or_then_and(self) -> None:
        """(Q(a=1) | Q(b=2)) & Q(c=3) produces correct tree."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        q3 = Q(c=3)

        or_branch = q1 | q2
        result = or_branch & q3

        # Top level is AND
        assert result.connector == Q.AND
        assert len(result.children) == 2
        # First child is the OR branch
        assert result.children[0] == or_branch
        assert result.children[0].connector == Q.OR
        # Second child is q3
        assert result.children[1] == q3

    def test_and_then_or(self) -> None:
        """Q(a=1) & Q(b=2) | Q(c=3) produces correct tree."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        q3 = Q(c=3)

        and_branch = q1 & q2
        result = and_branch | q3

        # Top level is OR
        assert result.connector == Q.OR
        assert len(result.children) == 2
        # First child is the AND branch
        assert result.children[0] == and_branch
        assert result.children[0].connector == Q.AND
        # Second child is q3
        assert result.children[1] == q3

    def test_negated_complex(self) -> None:
        """~((Q(a=1) | Q(b=2)) & Q(c=3)) produces correct tree."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        q3 = Q(c=3)

        complex_q = (q1 | q2) & q3
        result = ~complex_q

        assert result.negated is True
        assert len(result.children) == 1
        assert result.children[0] == complex_q


class TestQObjectRepr:
    """Test Q-object readable repr for debugging."""

    def test_repr_leaf_single(self) -> None:
        """repr(Q(country='US')) shows readable output."""
        q = Q(country="US")
        assert repr(q) == "Q(country='US')"

    def test_repr_leaf_multiple(self) -> None:
        """repr(Q(a=1, b=2)) shows sorted conditions."""
        q = Q(b=2, a=1)
        # Children sorted, so repr should be consistent
        r = repr(q)
        assert "a=1" in r
        assert "b=2" in r
        assert r.startswith("Q(")
        assert r.endswith(")")

    def test_repr_or(self) -> None:
        """repr(Q(a=1) | Q(b=2)) shows OR composition."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        result = q1 | q2
        assert repr(result) == "(Q(a=1) | Q(b=2))"

    def test_repr_and(self) -> None:
        """repr(Q(a=1) & Q(b=2)) shows AND composition."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        result = q1 & q2
        assert repr(result) == "(Q(a=1) & Q(b=2))"

    def test_repr_negated_leaf(self) -> None:
        """repr(~Q(a=1)) shows negation."""
        q = Q(a=1)
        result = ~q
        assert repr(result) == "~(Q(a=1))"

    def test_repr_negated_branch(self) -> None:
        """repr(~(Q(a=1) | Q(b=2))) shows negated composition."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        result = ~(q1 | q2)
        assert repr(result) == "~((Q(a=1) | Q(b=2)))"

    def test_repr_complex_nested(self) -> None:
        """repr((Q(a=1) | Q(b=2)) & Q(c=3)) shows full tree."""
        q1 = Q(a=1)
        q2 = Q(b=2)
        q3 = Q(c=3)
        result = (q1 | q2) & q3
        assert repr(result) == "((Q(a=1) | Q(b=2)) & Q(c=3))"


class TestQObjectBool:
    """Test Q-object truthiness."""

    def test_empty_q_is_falsy(self) -> None:
        """Q() with no children is falsy."""
        q = Q()
        assert not q
        assert bool(q) is False

    def test_q_with_conditions_is_truthy(self) -> None:
        """Q(a=1) with children is truthy."""
        q = Q(a=1)
        assert q
        assert bool(q) is True

    def test_composed_q_is_truthy(self) -> None:
        """Q(a=1) | Q(b=2) with children is truthy."""
        result = Q(a=1) | Q(b=2)
        assert result
        assert bool(result) is True
