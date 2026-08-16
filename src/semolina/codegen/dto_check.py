"""
Compare a committed DTO module against what the warehouse would produce today.

The DTO counterpart of :mod:`semolina.codegen.annotation_check`, which does the same job for
a committed ``SemanticView`` model. It answers one question per field: does the class you
committed still describe the result your query returns?

Two things are compared, not one. ``semolina codegen --check`` compares annotations, because
a model field has no alias. A generated DTO has both, and the alias is the half more likely
to move: it is the warehouse's own result-column spelling, so it changes when a metric is
renamed *and* when the file is regenerated against a different backend (the corrected D-04).
An annotation-only check would pass a Snowflake DTO deployed against Databricks, which is
the mistake the provenance header exists to make visible.

The generated side is never re-derived here. It comes from
:func:`semolina.codegen.dto_renderer._build_dto_context`, the same function the renderer
uses, so a check and a regeneration cannot disagree about what codegen would emit. That is
the same rule ``annotation_check`` follows when it decorates metric nullability through
``python_renderer.metric_annotation`` rather than inline, and for the same reason: the
per-backend metric spelling fixed in plan 50-01 is exactly the kind of thing a second copy
gets wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from semolina.codegen.annotation_check import ABSENT, STATUS_DRIFT, STATUS_MATCH
from semolina.codegen.dto_renderer import _build_dto_context

if TYPE_CHECKING:
    from semolina.codegen.dto_reader import CommittedDto
    from semolina.codegen.dto_renderer import ProbedQuery

_UNOPINIONATED = "Any"
"""
The annotation codegen emits when it has no opinion about a column's type.

Matches ``dto_renderer._UNMAPPED_ANNOTATION``. A field carrying it is emitted with a
``# TODO: <dtype>`` comment, and :ref:`the how-to <howto-dto-codegen>` tells the reader to
replace it with the type they want. :func:`_annotations_agree` honours that instruction --
see there for why an unopinionated generated annotation cannot drift.
"""


@dataclass(frozen=True)
class DtoFieldCheckRow:
    """
    One field's verdict.

    Attributes:
        name: The field name, as the generated class (or the committed one) spells it.
        committed_annotation: The annotation the committed DTO declares, or
            :data:`~semolina.codegen.annotation_check.ABSENT`.
        generated_annotation: The annotation codegen would emit, or
            :data:`~semolina.codegen.annotation_check.ABSENT`.
        committed_alias: The ``validation_alias`` the committed DTO declares, or
            :data:`~semolina.codegen.annotation_check.ABSENT`.
        generated_alias: The result column codegen resolved, or
            :data:`~semolina.codegen.annotation_check.ABSENT`.
        status: :data:`~semolina.codegen.annotation_check.STATUS_MATCH` or
            :data:`~semolina.codegen.annotation_check.STATUS_DRIFT`.
        detail: Why the row reads as it does when the four columns cannot show it -- an
            unopinionated generated annotation, or a field present on only one side. Empty
            when the columns are the whole story.
    """

    name: str
    committed_annotation: str
    generated_annotation: str
    committed_alias: str
    generated_alias: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class DtoCheckReport:
    """
    Every field's verdict for one generated DTO class.

    Attributes:
        class_name: The class checked.
        origin: Where the query came from, as the provenance header records it.
        route: The probe route that produced the generated side.
        rows: One row per field: generated fields in generated order, then any field the
            committed class declares that codegen would not emit.
        has_drift: True when any row drifted, or when the committed file declares no such
            class.
        absent: True when the committed file declares no class of this name at all. Kept
            separate from ``has_drift`` so the CLI can say "missing" rather than listing
            every field as drift with no explanation of why.
    """

    class_name: str
    origin: str
    route: str
    rows: list[DtoFieldCheckRow]
    has_drift: bool
    absent: bool = False


def _strip_optional(annotation: str) -> str:
    """
    Remove a trailing ``| None`` so the underlying annotation can be examined.

    Args:
        annotation: An annotation as written or as generated.

    Returns:
        The annotation without its optional suffix, whitespace-normalised.
    """
    parts = [part.strip() for part in annotation.split("|")]
    kept = [part for part in parts if part != "None"]
    return " | ".join(kept)


def _annotations_agree(committed: str, generated: str) -> tuple[bool, str]:
    """
    Decide whether a committed annotation still satisfies the generated one.

    Exact string equality, with one deliberate exception: a generated annotation of ``Any``
    agrees with anything. Codegen writes ``Any`` for an Arrow type its map has no entry for,
    and emits a ``# TODO: <dtype>`` comment telling the reader to replace it. Reporting drift
    against the edit the documentation instructs would make ``--check`` unusable for any DTO
    carrying such a column -- and it would be wrong on the merits, because ``Any`` is not a
    claim about the type that a narrower annotation could contradict.

    The exception is one-directional. A *committed* ``Any`` against a generated ``str`` is
    drift and is reported: there codegen has learned something the file does not know, and
    regenerating gains the reader a real annotation.

    ``| None`` is stripped from both sides before the comparison, so an unopinionated metric
    (``Any | None``) is recognised as unopinionated. Nullability itself is still compared:
    a generated ``str | None`` against a committed ``str`` differs as strings and drifts.

    Args:
        committed: The annotation the committed DTO declares.
        generated: The annotation codegen would emit.

    Returns:
        Whether they agree, and a detail string explaining any non-obvious verdict.
    """
    if committed == generated:
        return True, ""
    if _strip_optional(generated) == _UNOPINIONATED:
        return True, (
            f"codegen resolves {generated!r} for this column and has no opinion about it; "
            "the committed annotation is kept"
        )
    return False, ""


def check_dto(probed: ProbedQuery, committed: CommittedDto | None) -> DtoCheckReport:
    """
    Compare one probed query against the class a committed module declares for it.

    Fields are enumerated from the **generated** side first, then any extra the committed
    class declares. That order is what lets the two kinds of mismatch be told apart: a field
    the warehouse returns and the file does not declare is a stale committed class, while a
    field the file declares and the warehouse does not return is a field whose alias will
    never bind at ``.into()`` time.

    Args:
        probed: The probed query, carrying its schema and the dialect that built it.
        committed: The committed class of the same name, or None when the file declares
            none.

    Returns:
        The report. ``has_drift`` is True when any field differs or the class is absent.

    Raises:
        ValueError: If a projected field's alias cannot be resolved against the probed
            schema -- the same failure a generation run reports, raised from the same place.

    Example:
        .. code-block:: python

            from semolina.codegen.dto_check import check_dto

            report = check_dto(probed, committed)
            report.has_drift
            # False
    """
    context = _build_dto_context(probed)
    generated = {field.name: field for field in context.fields}

    rows: list[DtoFieldCheckRow] = []
    if committed is None:
        rows = [
            DtoFieldCheckRow(
                name=field.name,
                committed_annotation=ABSENT,
                generated_annotation=field.annotation,
                committed_alias=ABSENT,
                generated_alias=field.alias,
                status=STATUS_DRIFT,
                detail="no such class in the committed file",
            )
            for field in context.fields
        ]
        return DtoCheckReport(
            class_name=probed.class_name,
            origin=probed.origin,
            route=probed.route,
            rows=rows,
            has_drift=True,
            absent=True,
        )

    for field in context.fields:
        declared = committed.fields.get(field.name)
        if declared is None:
            rows.append(
                DtoFieldCheckRow(
                    name=field.name,
                    committed_annotation=ABSENT,
                    generated_annotation=field.annotation,
                    committed_alias=ABSENT,
                    generated_alias=field.alias,
                    status=STATUS_DRIFT,
                    detail="the query projects this field and the committed class omits it",
                )
            )
            continue

        agree, detail = _annotations_agree(declared.annotation, field.annotation)
        alias_agrees = declared.alias == field.alias
        if not alias_agrees:
            # Stated rather than left to the two alias columns, because the usual cause is
            # not a renamed metric: it is a file generated against one backend and checked
            # against another, which the columns alone read as an ordinary difference.
            detail = (
                "alias differs -- a DTO is pinned to the backend it was probed against"
                if not detail
                else f"{detail}; alias differs too"
            )
        rows.append(
            DtoFieldCheckRow(
                name=field.name,
                committed_annotation=declared.annotation,
                generated_annotation=field.annotation,
                committed_alias=declared.alias,
                generated_alias=field.alias,
                status=STATUS_MATCH if (agree and alias_agrees) else STATUS_DRIFT,
                detail=detail,
            )
        )

    for name, declared in committed.fields.items():
        if name in generated:
            continue
        rows.append(
            DtoFieldCheckRow(
                name=name,
                committed_annotation=declared.annotation,
                generated_annotation=ABSENT,
                committed_alias=declared.alias,
                generated_alias=ABSENT,
                status=STATUS_DRIFT,
                detail="the committed class declares this field and the query does not project it",
            )
        )

    return DtoCheckReport(
        class_name=probed.class_name,
        origin=probed.origin,
        route=probed.route,
        rows=rows,
        has_drift=any(row.status == STATUS_DRIFT for row in rows),
    )
