"""
Tests for reading a committed generated model's annotations without importing it.

The primary fixture is copied verbatim out of
``tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr`` so the parser is proven against
the exact source ``semolina codegen`` emits, not against a hand-written approximation of it.

The "does not execute" test is the one that matters most: ``--check`` is pointed at a file
path a user (or a CI job, on a repo checkout) supplies, and importing it would run whatever
that file's module level contains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from semolina.codegen.model_reader import read_committed_model

if TYPE_CHECKING:
    from pathlib import Path

# Copied from tests/unit/codegen/__snapshots__/test_codegen_e2e.ambr, snapshot
# `test_codegen_snowflake_field_types`. One metric with a stdlib-qualified annotation and a
# `| None` suffix, one dimension, one fact, and a raw-type `#` comment line above the metric.
SNOWFLAKE_SNAPSHOT_SOURCE = """\
import datetime
import decimal

from semolina import Dimension, Fact, Metric, SemanticView


class SalesView(SemanticView, view="sales_view"):
    # {"type": "FIXED", "scale": 0}
    revenue = Metric[decimal.Decimal | None]()
    country = Dimension[str]()
    date_key = Fact[datetime.date]()
"""


def _write(tmp_path: Path, source: str, name: str = "models.py") -> Path:
    """
    Write a fixture module and return its path.

    Args:
        tmp_path: pytest's per-test temporary directory.
        source: Python source to write.
        name: File name to write it under.

    Returns:
        Path to the written file.
    """
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return path


class TestReadsTheRenderersOwnOutput:
    """The parser is proven against the source the renderer actually emits."""

    def test_one_class_yields_one_model(self, tmp_path: Path) -> None:
        models = read_committed_model(_write(tmp_path, SNOWFLAKE_SNAPSHOT_SOURCE))

        assert len(models) == 1
        assert models[0].class_name == "SalesView"
        assert models[0].view_name == "sales_view"

    def test_fields_are_in_source_order(self, tmp_path: Path) -> None:
        models = read_committed_model(_write(tmp_path, SNOWFLAKE_SNAPSHOT_SOURCE))

        assert list(models[0].fields) == ["revenue", "country", "date_key"]

    def test_metric_annotation_is_recovered_exactly_as_written(self, tmp_path: Path) -> None:
        models = read_committed_model(_write(tmp_path, SNOWFLAKE_SNAPSHOT_SOURCE))

        revenue = models[0].fields["revenue"]
        assert revenue.name == "revenue"
        assert revenue.field_class == "Metric"
        assert revenue.annotation == "decimal.Decimal | None"
        assert revenue.source_name is None

    def test_dimension_and_fact_classes_are_recovered(self, tmp_path: Path) -> None:
        fields = read_committed_model(_write(tmp_path, SNOWFLAKE_SNAPSHOT_SOURCE))[0].fields

        assert fields["country"].field_class == "Dimension"
        assert fields["country"].annotation == "str"
        assert fields["date_key"].field_class == "Fact"
        assert fields["date_key"].annotation == "datetime.date"


def test_source_keyword_is_recovered(tmp_path: Path) -> None:
    source = """\
from semolina import Dimension, SemanticView


class V(SemanticView, view="v"):
    country = Dimension[str](source="COUNTRY")
"""
    field = read_committed_model(_write(tmp_path, source))[0].fields["country"]

    assert field.field_class == "Dimension"
    assert field.annotation == "str"
    assert field.source_name == "COUNTRY"


def test_alias_annotation_is_preserved_textually(tmp_path: Path) -> None:
    """A ``JsonValue`` annotation stays the name that was written, unresolved."""
    source = """\
from semolina import Dimension, JsonValue, SemanticView


class V(SemanticView, view="v"):
    payload = Dimension[JsonValue]()
"""
    field = read_committed_model(_write(tmp_path, source))[0].fields["payload"]

    assert field.annotation == "JsonValue"


def test_two_model_classes_yield_two_entries(tmp_path: Path) -> None:
    source = """\
from semolina import Dimension, Metric, SemanticView


class A(SemanticView, view="a_view"):
    revenue = Metric[int | None]()


class B(SemanticView, view="b_view"):
    country = Dimension[str]()
"""
    models = read_committed_model(_write(tmp_path, source))

    assert [m.view_name for m in models] == ["a_view", "b_view"]
    assert [m.class_name for m in models] == ["A", "B"]


def test_class_without_a_view_keyword_is_skipped(tmp_path: Path) -> None:
    """A plain class in the same file is not a generated model and must not crash the parse."""
    source = """\
from semolina import Dimension, SemanticView


class Helper:
    country = "not a field"


class V(SemanticView, view="v"):
    country = Dimension[str]()
"""
    models = read_committed_model(_write(tmp_path, source))

    assert [m.class_name for m in models] == ["V"]


def test_untyped_shorthand_reads_as_any(tmp_path: Path) -> None:
    """
    ``Metric()`` is the documented untyped shorthand and has no annotation to compare.

    It is represented as ``Any`` — the untyped fallback the renderer itself emits for an
    unmapped type — rather than dropped, so the field still appears in a drift report.
    """
    source = """\
from semolina import Metric, SemanticView


class V(SemanticView, view="v"):
    revenue = Metric()
"""
    field = read_committed_model(_write(tmp_path, source))[0].fields["revenue"]

    assert field.field_class == "Metric"
    assert field.annotation == "Any"


def test_non_field_assignments_are_skipped(tmp_path: Path) -> None:
    source = """\
from typing import ClassVar

from semolina import Dimension, SemanticView


class V(SemanticView, view="v"):
    label: ClassVar[str] = "v"
    other = dict[str, int]()
    country = Dimension[str]()
"""
    models = read_committed_model(_write(tmp_path, source))

    assert list(models[0].fields) == ["country"]


class TestErrorsAreCleanValueErrors:
    """A bad path or a bad file gives the CLI something to turn into an exit code."""

    def test_syntax_error_is_wrapped_naming_the_path(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "class V(SemanticView, view=:\n")

        with pytest.raises(ValueError, match=r"models\.py") as exc_info:
            read_committed_model(path)

        assert not isinstance(exc_info.value, SyntaxError)
        assert "line" in str(exc_info.value)

    def test_missing_file_is_wrapped_naming_the_path(self, tmp_path: Path) -> None:
        path = tmp_path / "nope.py"

        with pytest.raises(ValueError, match=r"nope\.py"):
            read_committed_model(path)


def test_module_level_code_is_not_executed(tmp_path: Path) -> None:
    """
    Parsing a model must run none of its module-level code.

    This is threat T-48-19 made runnable: ``--check`` reads a path the user supplies, and in
    CI that path comes from a repo checkout. The marker file is the evidence — if the module
    were imported or exec'd, it would exist.
    """
    marker = tmp_path / "MARKER"
    source = f"""\
import pathlib

from semolina import Dimension, SemanticView

pathlib.Path({str(marker)!r}).write_text("executed", encoding="utf-8")


class V(SemanticView, view="v"):
    country = Dimension[str]()
"""
    models = read_committed_model(_write(tmp_path, source))

    assert not marker.exists()
    assert [m.view_name for m in models] == ["v"]
