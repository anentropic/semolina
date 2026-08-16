"""
The DTO drift comparison, on hand-built schemas with no warehouse in the loop.

``check_dto`` takes a probed query and a committed class and answers per field. Everything
it reads is pure — the query object, the dialect, and a ``pyarrow.Schema`` — so the
interesting cases are reachable without a connection, including the per-backend alias
spellings that are the whole reason the alias half of the comparison exists.

The rule with the most judgement in it is :func:`~semolina.codegen.dto_check._annotations_agree`'s
carve-out for an unopinionated generated annotation, and it has its own class below. The
carve-out is not a convenience: the how-to instructs readers to replace a generated ``Any``
with a real type, so a comparison without it would report drift on the edit the
documentation asks for, and ``--check`` would be unusable for any DTO carrying a column the
Arrow map has no entry for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow
import pytest

from semolina.codegen.annotation_check import ABSENT, STATUS_DRIFT, STATUS_MATCH
from semolina.codegen.dto_check import DtoCheckReport, DtoFieldCheckRow, check_dto
from semolina.codegen.dto_reader import CommittedDto, CommittedDtoField
from semolina.codegen.dto_renderer import ProbedQuery
from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Sequence

    from semolina.query import _Query

CLASS_NAME = "ValueByRegion"
"""The generated class every case below compares against."""


def _query() -> _Query:
    """
    The probe view's headline projection: a decimal metric, a COUNT metric, a dimension.

    Returns:
        The query.
    """
    from type_fidelity_probe import TypeFidelityView as View

    return View.query().metrics(View.total_order_value, View.n_order_totals).dimensions(View.region)


def _probed(columns: Sequence[tuple[str, pyarrow.DataType]] | None = None) -> ProbedQuery:
    """
    Build a ``ProbedQuery`` over the DuckDB dialect from a hand-written schema.

    Args:
        columns: ``(name, type)`` pairs. Defaults to what DuckDB really returns for
            :func:`_query`.

    Returns:
        The record ``check_dto`` takes.
    """
    from semolina.dialect import Dialect, resolve_dialect

    if columns is None:
        columns = [
            ("total_order_value", pyarrow.decimal128(38, 2)),
            ("n_order_totals", pyarrow.int64()),
            ("region", pyarrow.string()),
        ]
    return ProbedQuery(
        class_name=CLASS_NAME,
        origin="myapp.queries.value_by_region",
        query=_query(),
        dialect=resolve_dialect(Dialect.DUCKDB),
        schema=pyarrow.schema([pyarrow.field(n, t) for n, t in columns]),
        route=ROUTE_EXECUTE_SCHEMA,
    )


def _committed(**fields: tuple[str, str]) -> CommittedDto:
    """
    Build a committed class from ``name=(annotation, alias)`` pairs.

    Args:
        **fields: One entry per declared field.

    Returns:
        The committed class.
    """
    return CommittedDto(
        class_name=CLASS_NAME,
        fields={
            name: CommittedDtoField(name=name, annotation=annotation, alias=alias)
            for name, (annotation, alias) in fields.items()
        },
    )


def _matching() -> CommittedDto:
    """
    The committed class codegen would generate for :func:`_probed` today.

    Returns:
        A class that must report no drift.
    """
    return _committed(
        total_order_value=("decimal.Decimal | None", "total_order_value"),
        n_order_totals=("int | None", "n_order_totals"),
        region=("str", "region"),
    )


def _row(report: DtoCheckReport, name: str) -> DtoFieldCheckRow:
    """
    Pull one field's row out of a report.

    Args:
        report: The report to read.
        name: The field name.

    Returns:
        The single row for that field.

    Raises:
        AssertionError: If the report carries no row for the field, or more than one.
    """
    rows = [r for r in report.rows if r.name == name]
    assert len(rows) == 1, f"expected one row for {name!r}, got {len(rows)}"
    return rows[0]


class TestAFileThatStillMatches:
    """The green path, which has to stay green or the check gets switched off."""

    def test_an_unchanged_class_reports_no_drift(self) -> None:
        """Every field matches, and ``has_drift`` is False."""
        report = check_dto(_probed(), _matching())

        assert not report.has_drift
        assert not report.absent
        assert [r.status for r in report.rows] == [STATUS_MATCH] * 3

    def test_the_report_carries_the_origin_and_route(self) -> None:
        """
        Both travel with the report so the CLI can print them under the table.

        The route matters for the same reason it does in the generated header: a check
        answered from the zero-row fallback and one answered from ``ExecuteSchema`` must not
        look identical.
        """
        report = check_dto(_probed(), _matching())

        assert report.origin == "myapp.queries.value_by_region"
        assert report.route == ROUTE_EXECUTE_SCHEMA


class TestAnnotationDrift:
    """The half ``semolina codegen --check`` also has."""

    def test_a_changed_annotation_drifts_and_shows_both_sides(self) -> None:
        """
        The committed and generated annotations are both carried, not just a verdict.

        A report saying only "drift" leaves the reader to regenerate and diff to find out
        what moved, which is the work the check was supposed to save.
        """
        committed = _matching()
        committed.fields["n_order_totals"] = CommittedDtoField(
            name="n_order_totals", annotation="float | None", alias="n_order_totals"
        )

        report = check_dto(_probed(), committed)
        row = _row(report, "n_order_totals")

        assert report.has_drift
        assert row.status == STATUS_DRIFT
        assert row.committed_annotation == "float | None"
        assert row.generated_annotation == "int | None"

    def test_dropping_the_optional_from_a_metric_drifts(self) -> None:
        """
        ``int`` against a generated ``int | None`` is drift, not a cosmetic difference.

        Every metric annotation carries ``| None`` (D-09) because a group whose inputs are
        all NULL returns NULL. A committed metric that dropped it is the narrow-annotation
        bug that stays invisible until the first NULL arrives, so the check must not treat
        nullability as noise -- even though the unopinionated carve-out strips ``| None``
        before deciding whether the *generated* side has an opinion.
        """
        committed = _matching()
        committed.fields["n_order_totals"] = CommittedDtoField(
            name="n_order_totals", annotation="int", alias="n_order_totals"
        )

        report = check_dto(_probed(), committed)

        assert report.has_drift
        assert _row(report, "n_order_totals").status == STATUS_DRIFT


class TestAliasDrift:
    """
    The half the sibling command has no equivalent for, because a model field has no alias.

    It is also the half more likely to move. An alias is the warehouse's own result-column
    spelling, so it changes when a metric is renamed *and* when the file is regenerated
    against a different backend -- and an annotation-only check would pass a Snowflake DTO
    deployed against Databricks, which is exactly what the provenance header exists to stop.
    """

    def test_a_changed_alias_drifts_even_when_the_annotation_matches(self) -> None:
        """The annotations agree, and the field still binds to the wrong column."""
        committed = _matching()
        committed.fields["region"] = CommittedDtoField(
            name="region", annotation="str", alias="REGION"
        )

        report = check_dto(_probed(), committed)
        row = _row(report, "region")

        assert report.has_drift
        assert row.status == STATUS_DRIFT
        assert row.committed_annotation == row.generated_annotation
        assert "alias differs" in row.detail

    def test_the_detail_names_backend_pinning_rather_than_a_rename(self) -> None:
        """
        The likeliest cause is a file generated elsewhere, and the message says so.

        "alias differs" alone reads as a renamed metric, which sends the reader to the
        warehouse. The usual cause is a DTO probed against another backend, which sends
        them to the header instead.
        """
        committed = _matching()
        committed.fields["region"] = CommittedDtoField(
            name="region", annotation="str", alias="REGION"
        )

        detail = _row(check_dto(_probed(), committed), "region").detail

        assert "pinned to the backend" in detail


class TestAFieldOnOnlyOneSide:
    """
    The two asymmetric mismatches, which mean different things and must read differently.

    Enumerating generated fields first and committed extras second is what lets them be
    told apart at all.
    """

    def test_a_projected_field_the_class_omits_is_drift(self) -> None:
        """The query returns a column the committed class cannot receive."""
        committed = _matching()
        del committed.fields["region"]

        report = check_dto(_probed(), committed)
        row = _row(report, "region")

        assert report.has_drift
        assert row.committed_annotation == ABSENT
        assert "omits it" in row.detail

    def test_a_declared_field_the_query_does_not_project_is_drift(self) -> None:
        """
        A leftover field's alias will never bind, and ``.into()`` reports it as missing.

        Catching it here is the point of the check: the alternative is finding out in a
        running service, where nothing points back at the generated file.
        """
        committed = _matching()
        committed.fields["stale"] = CommittedDtoField(name="stale", annotation="str", alias="STALE")

        report = check_dto(_probed(), committed)
        row = _row(report, "stale")

        assert report.has_drift
        assert row.generated_annotation == ABSENT
        assert "does not project it" in row.detail

    def test_a_class_the_file_does_not_declare_at_all_is_absent(self) -> None:
        """
        ``absent`` is separate from ``has_drift`` so the CLI can say "missing" once.

        Listing every field as drift with no explanation would bury the actual problem,
        which is that the class is not there.
        """
        report = check_dto(_probed(), None)

        assert report.absent
        assert report.has_drift
        assert all(r.committed_annotation == ABSENT for r in report.rows)


class TestAnUnopinionatedAnnotationCannotDrift:
    """
    A generated ``Any`` agrees with whatever the reader replaced it with.

    ``dto-codegen.rst`` tells the reader to search the generated file for ``TODO:`` and
    replace each ``Any`` with the type they want. A comparison by string equality would then
    report drift on every one of those edits, on every run, for ever -- so the check would be
    useless precisely for the files that needed the most hand-work.
    """

    def test_a_hand_narrowed_any_still_matches(self) -> None:
        """``list[str] | None`` against a generated ``Any | None`` is a match."""
        probed = _probed(
            [
                ("total_order_value", pyarrow.decimal128(38, 2)),
                ("n_order_totals", pyarrow.list_(pyarrow.string())),
                ("region", pyarrow.string()),
            ]
        )
        committed = _matching()
        committed.fields["n_order_totals"] = CommittedDtoField(
            name="n_order_totals", annotation="list[str] | None", alias="n_order_totals"
        )

        report = check_dto(probed, committed)

        assert not report.has_drift
        assert _row(report, "n_order_totals").status == STATUS_MATCH

    def test_the_row_says_why_it_matched(self) -> None:
        """
        A silent match here would look like agreement about the type, which it is not.

        The detail records that codegen has no opinion, so a reader scanning a green report
        can still see which annotations are theirs rather than the warehouse's.
        """
        probed = _probed(
            [
                ("total_order_value", pyarrow.decimal128(38, 2)),
                ("n_order_totals", pyarrow.list_(pyarrow.string())),
                ("region", pyarrow.string()),
            ]
        )
        committed = _matching()
        committed.fields["n_order_totals"] = CommittedDtoField(
            name="n_order_totals", annotation="list[str] | None", alias="n_order_totals"
        )

        detail = _row(check_dto(probed, committed), "n_order_totals").detail

        assert "no opinion" in detail

    def test_the_carve_out_does_not_excuse_a_changed_alias(self) -> None:
        """
        An unopinionated annotation says nothing about which column the field binds to.

        Letting ``Any`` wave through an alias mismatch would silence the half of the check
        that catches a DTO from the wrong backend.
        """
        probed = _probed(
            [
                ("total_order_value", pyarrow.decimal128(38, 2)),
                ("n_order_totals", pyarrow.list_(pyarrow.string())),
                ("region", pyarrow.string()),
            ]
        )
        committed = _matching()
        committed.fields["n_order_totals"] = CommittedDtoField(
            name="n_order_totals", annotation="list[str] | None", alias="N_ORDER_TOTALS"
        )

        report = check_dto(probed, committed)

        assert report.has_drift
        assert _row(report, "n_order_totals").status == STATUS_DRIFT

    def test_a_committed_any_against_a_resolved_type_still_drifts(self) -> None:
        """
        The carve-out is one-directional, and this is the direction it must not cover.

        Here codegen has learned a type the committed file does not know -- because the
        Arrow map gained an entry, say -- and regenerating gains the reader a real
        annotation. Treating it as a match would hide that for ever.
        """
        committed = _matching()
        committed.fields["region"] = CommittedDtoField(
            name="region", annotation="Any", alias="region"
        )

        report = check_dto(_probed(), committed)

        assert report.has_drift
        assert _row(report, "region").status == STATUS_DRIFT


class TestAnUnbindableAliasIsStillFatal:
    """A check cannot answer for a field that matches no result column."""

    def test_a_schema_missing_a_projected_column_raises(self) -> None:
        """
        The same ``ValueError`` a generation run reports, from the same place.

        There is no generated annotation to compare against, so reporting "drift" would be
        a verdict the check never reached. The CLI turns this into exit 6, matching what
        generating the same DTO would have done.
        """
        probed = _probed([("locale", pyarrow.string())])

        with pytest.raises(ValueError, match=r"matches no result column"):
            check_dto(probed, _matching())
