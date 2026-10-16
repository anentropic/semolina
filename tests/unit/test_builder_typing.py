"""
Prove that the query builder's parameter types catch misuse before the code runs.

Each builder method also checks its arguments at runtime, and ``test_query.py`` covers
that. What this module adds is the static half: a type checker reports
``.metrics(Sales.country)`` or ``.limit("10")`` at the call, in the user's editor, before
any query is built.

The claim is made non-vacuous the way ``test_dto_typecheck.py`` makes its own: every misuse
line must carry an error, and a twin file of correct calls must carry none. Without the
twin, a builder typed ``Never`` everywhere would pass; without the misuse lines, a builder
typed ``Any`` everywhere would.

Each misuse is its own parametrized case, so one that stops being reported fails on its own
rather than hiding behind another. Both files are checked once, by module-scoped fixtures,
because the cost is the subprocess and not the assertion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from typecheck import STRICT_REQUIRES_DEV_GROUP, basedpyright_available, type_check

if TYPE_CHECKING:
    from pathlib import Path

_MODEL = """\
from semolina import Dimension, Fact, Metric, SemanticView


class Sales(SemanticView, view="sales"):
    revenue = Metric[int]()
    country = Dimension[str]()
    unit_price = Fact[float]()


q = Sales.query()
"""

MISUSES = {
    "a dimension passed to metrics()": "q.metrics(Sales.country)",
    "a fact passed to metrics()": "q.metrics(Sales.unit_price)",
    "a metric passed to dimensions()": "q.dimensions(Sales.revenue)",
    "a string passed to metrics()": 'q.metrics("revenue")',
    "a string passed to order_by()": 'q.order_by("revenue")',
    "a string passed to limit()": 'q.limit("10")',
    "a float passed to limit()": "q.limit(10.0)",
    "an int passed to using()": "q.using(1)",
    "a string passed to where()": "q.where(\"country = 'US'\")",
}
"""Each misuse, keyed by the case name, as the one line of source that commits it."""

CORRECT = [
    "q.metrics(Sales.revenue)",
    "q.dimensions(Sales.country, Sales.unit_price)",
    "q.order_by(Sales.revenue, Sales.country.desc())",
    "q.limit(10)",
    'q.using("warehouse")',
    "q.where(Sales.country == 'US', None)",
    "q.metrics(Sales.revenue).dimensions(Sales.country).order_by(Sales.revenue).limit(5)",
]
"""Every builder method called correctly, so a too-narrow signature is an error here."""


def _misuse_source() -> tuple[str, dict[str, int]]:
    """
    Build the misuse file and record the line each case lands on.

    Returns:
        The source text, and each case name mapped to its 1-based line number.
    """
    lines: list[str] = list(_MODEL.splitlines())
    where: dict[str, int] = {}
    for name, call in MISUSES.items():
        lines.append(call)
        where[name] = len(lines)
    return "\n".join(lines) + "\n", where


@pytest.fixture(scope="module")
def misuse_report(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Type-check the misuse file once for every case."""
    workdir: Path = tmp_path_factory.mktemp("builder_misuse")
    source, where = _misuse_source()
    return type_check(workdir, {"misuse.py": source}, "misuse.py"), where


@pytest.fixture(scope="module")
def correct_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Type-check the correct-usage file once."""
    workdir: Path = tmp_path_factory.mktemp("builder_correct")
    source = _MODEL + "\n".join(CORRECT) + "\n"
    return type_check(workdir, {"correct.py": source}, "correct.py")


def _error_lines(report: dict[str, Any]) -> set[int]:
    """
    Return the 1-based lines basedpyright reported an error on.

    Args:
        report: A parsed basedpyright JSON report.

    Returns:
        The set of lines carrying at least one error.
    """
    diagnostics: list[dict[str, Any]] = report["generalDiagnostics"]
    return {
        int(d["range"]["start"]["line"]) + 1 for d in diagnostics if d.get("severity") == "error"
    }


@pytest.mark.skipif(not basedpyright_available(), reason=STRICT_REQUIRES_DEV_GROUP)
@pytest.mark.parametrize("case", list(MISUSES))
def test_misuse_is_reported_at_the_call(
    case: str, misuse_report: tuple[dict[str, Any], dict[str, int]]
) -> None:
    """Each misuse carries a type error on its own line."""
    report, where = misuse_report
    assert where[case] in _error_lines(report), (
        f"{MISUSES[case]!r} type-checked clean; diagnostics: {report['generalDiagnostics']}"
    )


@pytest.mark.skipif(not basedpyright_available(), reason=STRICT_REQUIRES_DEV_GROUP)
def test_misuse_errors_land_only_on_misuse_lines(
    misuse_report: tuple[dict[str, Any], dict[str, int]],
) -> None:
    """The model and the query above the misuses type-check clean, so no error is borrowed."""
    report, where = misuse_report
    assert _error_lines(report) <= set(where.values()), report["generalDiagnostics"]


@pytest.mark.skipif(not basedpyright_available(), reason=STRICT_REQUIRES_DEV_GROUP)
def test_correct_usage_type_checks_clean(correct_report: dict[str, Any]) -> None:
    """Every builder method called correctly carries no error, under stock strict."""
    assert correct_report["summary"]["errorCount"] == 0, correct_report["generalDiagnostics"]
