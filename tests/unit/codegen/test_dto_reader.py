"""
The committed-DTO reader, tested on source text rather than on an importable module.

``read_committed_dtos`` parses and never imports, which is the property most of this module
exists to pin. The file it reads is codegen's own *output*: it may have been hand-edited, it
may sit outside any package, and in CI it is read by a process that need not have pydantic
or arrowmodel installed. A reader that imported it would fail on all three.

What counts as a generated DTO class is deliberately keyed on the shape the renderer emits —
a field assigned ``pydantic.Field(validation_alias=...)`` — rather than on the base class.
The tests below pin that choice from both directions: a class carrying the shape is read
however its base is spelled, and a class without it is skipped however convincing its base
looks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from semolina.codegen.dto_reader import read_committed_dtos

if TYPE_CHECKING:
    from pathlib import Path

GENERATED = '''
"""
Generated result DTOs. Do not edit.

Backend: snowflake
"""

from __future__ import annotations

import decimal
from typing import Any

import pydantic


class RevenueByCountry(pydantic.BaseModel):
    """Result DTO for myapp.queries.revenue_by_country (probe route: execute-schema)."""

    revenue: decimal.Decimal | None = pydantic.Field(validation_alias='AGG("REVENUE")')
    country: str = pydantic.Field(validation_alias="COUNTRY")


class OrdersByMonth(pydantic.BaseModel):
    """Result DTO for myapp.queries.orders_by_month (probe route: zero-row)."""

    # TODO: list<l: string>
    tags: Any | None = pydantic.Field(validation_alias="TAGS")
'''
"""
A committed module in exactly the shape the renderer emits.

Includes the two things a naive parser trips on: a docstring as the first class-body
statement, and a ``# TODO:`` comment between the fields of the second class.
"""


def _write(tmp_path: Path, source: str, name: str = "dtos.py") -> Path:
    """
    Write a DTO module and return its path.

    Args:
        tmp_path: pytest's per-test temporary directory.
        source: The module source.
        name: The file name.

    Returns:
        The written path.
    """
    path = tmp_path / name
    path.write_text(source)
    return path


class TestReadingAGeneratedModule:
    """The happy path, over source the renderer really produces."""

    def test_every_class_and_field_is_read_in_source_order(self, tmp_path: Path) -> None:
        """
        Two classes, their fields, annotations and aliases.

        Order is asserted because it is the order the check report walks, and a reader
        returning a dict-of-classes would lose it.
        """
        dtos = read_committed_dtos(_write(tmp_path, GENERATED))

        assert [d.class_name for d in dtos] == ["RevenueByCountry", "OrdersByMonth"]
        assert list(dtos[0].fields) == ["revenue", "country"]
        assert dtos[0].fields["revenue"].annotation == "decimal.Decimal | None"
        assert dtos[0].fields["country"].annotation == "str"

    def test_an_alias_carrying_a_double_quote_survives(self, tmp_path: Path) -> None:
        """
        ``AGG("REVENUE")`` is the normal Snowflake spelling, and it is the awkward one.

        The renderer writes it as a single-quoted literal because the value contains double
        quotes. A reader that matched on source text rather than on the parsed constant
        would return the quotes along with it, and every Snowflake check would then drift
        on every metric.
        """
        dtos = read_committed_dtos(_write(tmp_path, GENERATED))

        assert dtos[0].fields["revenue"].alias == 'AGG("REVENUE")'
        assert dtos[0].fields["country"].alias == "COUNTRY"

    def test_a_todo_comment_does_not_break_the_field_after_it(self, tmp_path: Path) -> None:
        """
        The ``# TODO:`` line the renderer emits above an unmapped field is not a statement.

        It is invisible to the AST, which is the point: the reader sees the ``AnnAssign``
        that follows it exactly as it sees any other.
        """
        dtos = read_committed_dtos(_write(tmp_path, GENERATED))

        assert dtos[1].fields["tags"].annotation == "Any | None"
        assert dtos[1].fields["tags"].alias == "TAGS"

    def test_the_file_is_parsed_and_never_imported(self, tmp_path: Path) -> None:
        """
        A module that would fail on import is still read.

        The committed DTO file is codegen's output, read in CI by a process that need not
        have its imports installed -- and a module-level ``raise`` is the cheapest proof
        that nothing in it ran.
        """
        source = GENERATED.replace(
            "import pydantic",
            "import pydantic\n\nraise RuntimeError('this module was imported')",
        )

        dtos = read_committed_dtos(_write(tmp_path, source))

        assert [d.class_name for d in dtos] == ["RevenueByCountry", "OrdersByMonth"]

    def test_an_import_alias_for_pydantic_reads_the_same(self, tmp_path: Path) -> None:
        """
        ``from pydantic import BaseModel, Field`` is a hand-edit the reader must survive.

        Fields are recognized by the ``validation_alias`` keyword rather than by the
        callee's spelling, so a file someone tidied still checks. Keying on
        ``pydantic.Field`` would have made a cosmetic edit look like a deleted class.
        """
        source = (
            "from pydantic import BaseModel, Field\n\n\n"
            "class RevenueByCountry(BaseModel):\n"
            "    country: str = Field(validation_alias='COUNTRY')\n"
        )

        dtos = read_committed_dtos(_write(tmp_path, source))

        assert [d.class_name for d in dtos] == ["RevenueByCountry"]
        assert dtos[0].fields["country"].alias == "COUNTRY"


class TestWhatIsNotAGeneratedDto:
    """Classes the reader must leave out, so a check reports on generated classes only."""

    def test_a_class_with_no_aliased_fields_is_skipped(self, tmp_path: Path) -> None:
        """
        A hand-written Pydantic model sharing the module is not codegen's to check.

        Reporting it would say a class the user wrote is "extra", which is both wrong and
        the kind of noise that gets a CI check switched off.
        """
        source = (
            "import pydantic\n\n\n"
            "class HandWritten(pydantic.BaseModel):\n"
            "    total: int\n"
            "    label: str = 'x'\n"
        )

        assert read_committed_dtos(_write(tmp_path, source)) == []

    def test_a_field_with_no_validation_alias_is_skipped(self, tmp_path: Path) -> None:
        """
        ``pydantic.Field(default=0)`` is a field, and not one codegen emits.

        The class is still read when it carries at least one aliased field; only the
        unaliased declaration is left out, because there is no result column to compare it
        against.
        """
        source = (
            "import pydantic\n\n\n"
            "class Mixed(pydantic.BaseModel):\n"
            "    country: str = pydantic.Field(validation_alias='COUNTRY')\n"
            "    extra: int = pydantic.Field(default=0)\n"
        )

        dtos = read_committed_dtos(_write(tmp_path, source))

        assert list(dtos[0].fields) == ["country"]

    def test_the_multi_alias_form_is_not_read(self, tmp_path: Path) -> None:
        """
        ``AliasChoices(...)`` is not a plain string, and the renderer never emits it.

        Semolina's own ``.into()`` pre-check skips such a field with no verdict and
        arrowmodel refuses it outright, so a reader that accepted it would let a check pass
        a class that cannot be used.
        """
        source = (
            "import pydantic\n\n\n"
            "class Multi(pydantic.BaseModel):\n"
            "    country: str = pydantic.Field(\n"
            "        validation_alias=pydantic.AliasChoices('COUNTRY', 'country')\n"
            "    )\n"
        )

        assert read_committed_dtos(_write(tmp_path, source)) == []


class TestAFileThatCannotBeRead:
    """Both failures report as this reader's own ValueError, naming the path."""

    def test_a_missing_file_names_the_path(self, tmp_path: Path) -> None:
        """A path that does not exist is the caller's to fix, not a traceback."""
        with pytest.raises(ValueError, match=r"Cannot read DTO file .*dtos.py"):
            read_committed_dtos(tmp_path / "dtos.py")

    def test_a_syntax_error_names_the_line(self, tmp_path: Path) -> None:
        """
        The line number is the actionable part of a parse failure.

        A committed DTO module is normally machine-written, so a syntax error in one means
        a hand-edit went wrong, and the reader's job is to say where.
        """
        with pytest.raises(ValueError, match=r"Cannot parse DTO file .* at line 1"):
            read_committed_dtos(_write(tmp_path, "class X(:\n"))
