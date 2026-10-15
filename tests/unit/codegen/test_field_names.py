"""
Tests for the rule that turns warehouse column names into generated field names.

``semolina codegen`` writes one attribute per column. A column name is the warehouse's to
choose and need not be a Python identifier (``what?``, ``Order Date``, ``class``), so the
rule in :func:`semolina.codegen.introspector.python_field_names` makes each one valid and
unique, and :func:`semolina.codegen.introspector.with_python_field_names` keeps the original
spelling in ``source=`` wherever the name changed.

The helpers are imported inside each test rather than at module level, so that a missing
helper fails every case on its own instead of failing the module at collection.
"""

from __future__ import annotations

import ast

import pytest

from semolina.codegen.introspector import IntrospectedField, IntrospectedView


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        pytest.param("what?", "what_", id="punctuation"),
        pytest.param("order date", "order_date", id="space"),
        pytest.param("net-revenue ($)", "net_revenue____", id="several-invalid"),
        pytest.param("class", "class_", id="keyword"),
        pytest.param("none", "none", id="lowercase-none-is-not-a-keyword"),
        pytest.param("match", "match_", id="soft-keyword"),
        pytest.param("type", "type_", id="soft-keyword-type"),
        pytest.param("1st", "_1st", id="digit-start"),
        pytest.param("2024 sales", "_2024_sales", id="digit-start-and-space"),
        pytest.param("?", "column", id="all-invalid"),
        pytest.param("", "column", id="empty"),
        pytest.param("_", "column", id="lone-underscore"),
        pytest.param("query", "query_", id="reserved-builder-name"),
        pytest.param("keys", "keys_", id="reserved-dict-name"),
        pytest.param("_fields", "_fields_", id="base-class-attribute"),
        pytest.param("__init__", "_init__", id="dunder"),
        pytest.param("__secret", "_secret", id="name-mangled"),
        pytest.param("café", "café", id="non-ascii-letters-kept"),
        pytest.param("ﬁeld", "field", id="nfkc-normalized"),
        pytest.param("revenue", "revenue", id="valid-unchanged"),
        pytest.param("Revenue", "Revenue", id="case-kept"),
    ],
)
def test_single_name(column: str, expected: str) -> None:
    """Each column name maps to one valid, usable field name."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names([column]) == [expected]


@pytest.mark.parametrize(
    "column",
    ["what?", "order date", "class", "match", "1st", "?", "", "query", "__init__", "ﬁeld"],
)
def test_result_is_a_declarable_field_name(column: str) -> None:
    """Every result passes the same check a model field declaration applies."""
    from semolina.codegen.introspector import python_field_names
    from semolina.codegen.query_resolver import is_valid_field_name

    (name,) = python_field_names([column])
    assert is_valid_field_name(name), name


def test_collision_after_sanitizing_takes_suffix_in_column_order() -> None:
    """Two columns that sanitize alike are numbered in column order."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names(["a b", "a-b", "a.b"]) == ["a_b", "a_b_2", "a_b_3"]


def test_collision_with_an_existing_valid_name_keeps_the_valid_name() -> None:
    """A column already spelled as a valid name keeps it; the renamed one is numbered."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names(["a b", "a_b"]) == ["a_b_2", "a_b"]


def test_suffix_skips_a_name_another_column_already_has() -> None:
    """The suffix never lands on a name a later column carries verbatim."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names(["a b", "a-b", "a_b_2"]) == ["a_b", "a_b_3", "a_b_2"]


def test_all_invalid_names_are_numbered() -> None:
    """Several all-invalid names become ``column``, ``column_2`` and so on."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names(["?", "!", ""]) == ["column", "column_2", "column_3"]


def test_suffix_follows_the_keyword_fix() -> None:
    """A keyword's trailing underscore is not doubled when a suffix is added."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names(["class", "class?"]) == ["class_", "class_2"]


def test_duplicate_valid_names_are_numbered() -> None:
    """Two columns folding to one valid name (``ORDER_ID``, ``order_id``) still differ."""
    from semolina.codegen.introspector import python_field_names

    assert python_field_names(["order_id", "order_id"]) == ["order_id", "order_id_2"]


def test_result_is_deterministic() -> None:
    """The same input always yields the same names."""
    from semolina.codegen.introspector import python_field_names

    columns = ["what?", "what_", "?", "1st", "class", "a b", "a_b"]
    assert python_field_names(columns) == python_field_names(list(columns))


def _dimension(name: str, source_name: str | None = None) -> IntrospectedField:
    """Build a string dimension field."""
    return IntrospectedField(
        name=name, field_type="dimension", data_type="str", source_name=source_name
    )


def test_with_python_field_names_sets_source_on_renamed_fields_only() -> None:
    """A renamed field reads its exact column through ``source``; an unchanged one is kept."""
    from semolina.codegen.introspector import with_python_field_names

    fields = [_dimension("what?"), _dimension("country"), _dimension("order date")]
    named = with_python_field_names(fields, ["what?", "country", "ORDER DATE"])

    assert [(f.name, f.source_name) for f in named] == [
        ("what_", "what?"),
        ("country", None),
        ("order_date", "ORDER DATE"),
    ]


def test_with_python_field_names_keeps_an_existing_source() -> None:
    """An unchanged field keeps the ``source`` its engine already set."""
    from semolina.codegen.introspector import with_python_field_names

    fields = [_dimension("mymetric", source_name="MyMetric")]
    named = with_python_field_names(fields, ["MyMetric"])

    assert [(f.name, f.source_name) for f in named] == [("mymetric", "MyMetric")]


def test_with_python_field_names_rejects_mismatched_lengths() -> None:
    """One column per field: a mismatch is a programming error, not a silent truncation."""
    from semolina.codegen.introspector import with_python_field_names

    with pytest.raises(ValueError):
        with_python_field_names([_dimension("a")], ["a", "b"])


class TestRenderedNames:
    """Sanitized names render as valid Python that reads the original column."""

    def _render(self, columns: list[str]) -> str:
        """Name string dimensions after ``columns`` and render them as one model."""
        from semolina.codegen.introspector import with_python_field_names
        from semolina.codegen.python_renderer import render_views

        fields = with_python_field_names([_dimension(c) for c in columns], columns)
        view = IntrospectedView(view_name="odd_view", class_name="OddView", fields=fields)
        return render_views([view])

    @pytest.mark.parametrize(
        ("column", "line"),
        [
            pytest.param("what?", 'what_ = Dimension[str](source="what?")', id="punctuation"),
            pytest.param(
                "order date", 'order_date = Dimension[str](source="order date")', id="space"
            ),
            pytest.param("class", 'class_ = Dimension[str](source="class")', id="keyword"),
            pytest.param("1st", '_1st = Dimension[str](source="1st")', id="digit-start"),
            pytest.param("?", 'column = Dimension[str](source="?")', id="all-invalid"),
            pytest.param('say "hi"', "say__hi_ = Dimension[str](source='say \"hi\"')", id="quote"),
        ],
    )
    def test_renders_sanitized_name_with_source(self, column: str, line: str) -> None:
        """The field line carries the sanitized name and the exact column as ``source``."""
        source = self._render([column])
        assert line in source, source
        ast.parse(source)

    def test_collision_renders_two_fields(self) -> None:
        """Colliding columns render as two distinct attributes, each with its source."""
        source = self._render(["a b", "a-b"])
        assert 'a_b = Dimension[str](source="a b")' in source, source
        assert 'a_b_2 = Dimension[str](source="a-b")' in source, source

    def test_rendered_module_defines_a_working_model(self) -> None:
        """The rendered module executes, and each field resolves to its original column."""
        columns = ["what?", "order date", "class", "1st", "?", "a b", "a-b", "query"]
        source = self._render(columns)
        namespace: dict[str, object] = {}
        exec(compile(source, "<generated>", "exec"), namespace)

        from semolina import SemanticView

        model = namespace["OddView"]
        assert isinstance(model, type)
        assert issubclass(model, SemanticView)
        assert [f.source for f in model._fields.values()] == columns
