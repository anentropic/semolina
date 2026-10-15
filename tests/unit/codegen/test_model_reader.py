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

from semolina.codegen.model_reader import (
    normalize_view_name,
    read_committed_model,
    read_committed_model_file,
)

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

    The threat made runnable: ``--check`` reads a path the user supplies, and in
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


# ---------------------------------------------------------------------------
# D9: names, bases and constants resolve; nothing field-like is skipped silently
# ---------------------------------------------------------------------------


def _package(tmp_path: Path, files: dict[str, str]) -> None:
    """
    Write a package tree under ``tmp_path``.

    Args:
        tmp_path: The project root.
        files: Relative path -> source.
    """
    for relative, source in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


class TestAnnotationsAreAlsoRecordedResolved:
    """The written annotation is kept for the report; its resolved form is what is compared."""

    def test_an_imported_name_resolves(self, tmp_path: Path) -> None:
        source = """\
from decimal import Decimal
from typing import Optional

from semolina import Metric, SemanticView


class V(SemanticView, view="v"):
    revenue = Metric[Optional[Decimal]]()
"""
        field = read_committed_model(_write(tmp_path, source))[0].fields["revenue"]

        assert field.annotation == "Optional[Decimal]"
        assert field.resolved_annotation == "decimal.Decimal | None"

    def test_a_name_from_the_users_own_module_is_left_unresolved(self, tmp_path: Path) -> None:
        source = """\
from semolina import Dimension, SemanticView

from app.types import Money


class V(SemanticView, view="v"):
    price = Dimension[Money]()
"""
        field = read_committed_model(_write(tmp_path, source))[0].fields["price"]

        assert field.annotation == "Money"
        assert field.resolved_annotation is None


class TestInheritedFields:
    """Fields declared on a base class read as the subclass's own (M6)."""

    def test_a_subclass_declaration_replaces_its_bases(self, tmp_path: Path) -> None:
        source = """\
from semolina import Dimension, Metric, SemanticView


class Base(SemanticView, abstract=True):
    region = Dimension[str]()
    revenue = Metric[int | None]()


class V(Base, view="v"):
    revenue = Metric[float | None]()
"""
        read = read_committed_model_file(_write(tmp_path, source))

        assert [m.class_name for m in read.models] == ["V"]
        fields = read.models[0].fields
        assert list(fields) == ["region", "revenue"]
        assert fields["revenue"].annotation == "float | None"
        assert read.warnings == []

    def test_a_base_reexported_through_a_package_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _package(
            tmp_path,
            {
                "app/__init__.py": "from app.base import Base\n",
                "app/base.py": (
                    "from semolina import Dimension, SemanticView\n\n\n"
                    "class Base(SemanticView, abstract=True):\n"
                    "    region = Dimension[str]()\n"
                ),
                "app/models.py": (
                    "from semolina import Metric\n\nfrom app import Base\n\n\n"
                    'class V(Base, view="v"):\n'
                    "    revenue = Metric[int | None]()\n"
                ),
            },
        )
        monkeypatch.chdir(tmp_path)

        read = read_committed_model_file(tmp_path / "app" / "models.py")

        assert list(read.models[0].fields) == ["region", "revenue"]
        assert read.warnings == []

    def test_a_relative_import_in_a_src_layout(self, tmp_path: Path) -> None:
        """The package root is found from ``__init__.py`` files, not from the working directory."""
        _package(
            tmp_path,
            {
                "src/app/__init__.py": "",
                "src/app/base.py": (
                    "from semolina import Dimension, SemanticView\n\n\n"
                    "class Base(SemanticView, abstract=True):\n"
                    "    region = Dimension[str]()\n"
                ),
                "src/app/models.py": (
                    'from .base import Base\n\n\nclass V(Base, view="v"):\n    pass\n'
                ),
            },
        )

        read = read_committed_model_file(tmp_path / "src" / "app" / "models.py")

        assert list(read.models[0].fields) == ["region"]

    def test_imported_modules_are_parsed_and_never_executed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Following a base into another module runs none of that module either."""
        marker = tmp_path / "MARKER"
        _package(
            tmp_path,
            {
                "app/__init__.py": f"import pathlib\npathlib.Path({str(marker)!r}).touch()\n",
                "app/base.py": (
                    "import pathlib\n"
                    "from semolina import Dimension, SemanticView\n\n"
                    f"pathlib.Path({str(marker)!r}).touch()\n\n\n"
                    "class Base(SemanticView, abstract=True):\n"
                    "    region = Dimension[str]()\n"
                ),
                "app/models.py": (
                    'from app.base import Base\n\n\nclass V(Base, view="v"):\n    pass\n'
                ),
            },
        )
        monkeypatch.chdir(tmp_path)

        read = read_committed_model_file(tmp_path / "app" / "models.py")

        assert not marker.exists()
        assert list(read.models[0].fields) == ["region"]

    def test_a_base_that_cannot_be_found_is_warned_about(self, tmp_path: Path) -> None:
        source = """\
from semolina import Metric

from somewhere_else import Base


class V(Base, view="v"):
    revenue = Metric[int | None]()
"""
        read = read_committed_model_file(_write(tmp_path, source))

        assert list(read.models[0].fields) == ["revenue"]
        assert len(read.warnings) == 1
        assert "V" in read.warnings[0]
        assert "Base" in read.warnings[0]
        assert "not followed" in read.warnings[0]


class TestViewFromAConstant:
    """``view=`` may name a string constant, however it is reached (M3)."""

    def test_a_constant_reached_through_a_module_attribute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _package(
            tmp_path,
            {
                "app/__init__.py": "",
                "app/names.py": 'SALES_VIEW = "sales_view"\n',
                "app/models.py": (
                    "from semolina import Dimension, SemanticView\n\nfrom app import names\n\n\n"
                    "class V(SemanticView, view=names.SALES_VIEW):\n"
                    "    region = Dimension[str]()\n"
                ),
            },
        )
        monkeypatch.chdir(tmp_path)

        models = read_committed_model(tmp_path / "app" / "models.py")

        assert [m.view_name for m in models] == ["sales_view"]

    def test_a_view_that_is_not_a_string_is_warned_about(self, tmp_path: Path) -> None:
        source = """\
from semolina import Dimension, SemanticView


class V(SemanticView, view=make_name()):
    region = Dimension[str]()
"""
        read = read_committed_model_file(_write(tmp_path, source))

        assert read.models == []
        assert len(read.warnings) == 1
        assert "V" in read.warnings[0]
        assert "make_name()" in read.warnings[0]


class TestNothingFieldLikeIsSkippedSilently:
    """
    GEN-12: a statement that might declare a field is read or warned about, never dropped.

    Each case is one the reader cannot read. Before D9 every one of them vanished, and the
    field then read as absent with nothing saying why.
    """

    @pytest.mark.parametrize(
        ("statement", "fragment"),
        [
            ("    revenue = Helper[int]()\n", "Helper[int]()"),
            ("    revenue, cost = Metric[int](), Metric[int]()\n", "revenue, cost"),
            ("    revenue = cost = Metric[int]()\n", "revenue = cost"),
            ("    if True:\n        revenue = Metric[int]()\n", "if True"),
            ("    revenue: Metric[int]\n", "revenue: Metric[int]"),
            ("    revenue = Metric[int](source=column_name())\n", "source="),
        ],
        ids=[
            "unknown-constructor",
            "tuple-assignment",
            "chained-assignment",
            "inside-an-if",
            "annotation-only",
            "source-not-a-string",
        ],
    )
    def test_an_unread_statement_is_warned_about(
        self, tmp_path: Path, statement: str, fragment: str
    ) -> None:
        source = (
            "from semolina import Dimension, Metric, SemanticView\n\n\n"
            'class V(SemanticView, view="v"):\n'
            "    region = Dimension[str]()\n" + statement
        )

        read = read_committed_model_file(_write(tmp_path, source))

        assert len(read.warnings) == 1, read.warnings
        assert read.warnings[0].startswith("V (line ")
        assert fragment in read.warnings[0]

    def test_a_nested_class_with_a_view_is_warned_about(self, tmp_path: Path) -> None:
        source = """\
from semolina import Dimension, SemanticView

if True:

    class V(SemanticView, view="v"):
        region = Dimension[str]()
"""
        read = read_committed_model_file(_write(tmp_path, source))

        assert read.models == []
        assert len(read.warnings) == 1
        assert "V" in read.warnings[0]

    def test_statements_known_not_to_be_fields_are_not_warned_about(self, tmp_path: Path) -> None:
        """A builtin, a ``ClassVar`` and a docstring cannot declare a field, so stay quiet."""
        source = """\
from typing import ClassVar

from semolina import Dimension, SemanticView


class V(SemanticView, view="v"):
    \"\"\"A view.\"\"\"

    label: ClassVar[str] = "v"
    other = dict[str, int]()
    country = Dimension[str]()
    \"\"\"The country.\"\"\"
"""
        read = read_committed_model_file(_write(tmp_path, source))

        assert list(read.models[0].fields) == ["country"]
        assert read.warnings == []

    def test_the_renderers_own_output_reads_without_a_warning(self, tmp_path: Path) -> None:
        read = read_committed_model_file(_write(tmp_path, SNOWFLAKE_SNAPSHOT_SOURCE))

        assert read.warnings == []


class TestViewNamesFoldLikeDuckDB:
    """M4: a view name matches across case, quoting and DuckDB's default schema."""

    @pytest.mark.parametrize(
        ("name", "folded"),
        [
            ("sales_view", "sales_view"),
            ("SALES_VIEW", "sales_view"),
            ('"Sales_View"', "sales_view"),
            ("main.sales_view", "sales_view"),
            ('MAIN."sales_view"', "sales_view"),
            ("analytics.sales_view", "analytics.sales_view"),
            ('"my.view"', "my.view"),
            ('"say ""hi"""', 'say "hi"'),
        ],
    )
    def test_folding(self, name: str, folded: str) -> None:
        assert normalize_view_name(name) == folded


@pytest.mark.parametrize("name", ["models.v2.py", "models.py.bak"])
def test_a_file_stem_with_a_dot_reads_without_crashing(tmp_path: Path, name: str) -> None:
    """``models.v2.py`` has no ``models`` package beside it; it is still read on its own."""
    models = read_committed_model(_write(tmp_path, SNOWFLAKE_SNAPSHOT_SOURCE, name=name))

    assert [m.class_name for m in models] == ["SalesView"]
