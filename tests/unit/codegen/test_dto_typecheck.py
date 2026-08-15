"""
Prove DTO-08 by measurement: the generated DTO type-checks under strict, with no ignores.

DTO-08 is the one requirement in this phase that can be faked three ways -- by suppressing
the errors, by running a weaker configuration, or by silently skipping when the tool is
absent. Each of those reads green. So every assertion here is paired with something that
shows the check *can* fail:

* The type check asserts ``summary.errorCount``, never the process exit code. A file whose
  errors are suppressed by a comment still exits 0, which is precisely the hole a
  suppression would walk through.
* "No ignores" is asserted on the rendered string, not on the type checker, for the same
  reason: a suppressed error is invisible to the thing being asked.
* A negative control -- a deliberately unannotated function -- must report a non-zero error
  count. Without it a broken invocation would report zero errors forever.
* That same control also proves *which* configuration is in effect. It trips
  ``reportUnknownVariableType``, a rule ``pyproject.toml`` disables, so the diagnostic could
  not have come from Semolina's own config.

**The posture here deliberately differs from** ``python_renderer.ruff_available``. That guard
degrades silently in shipped code, which is right for a formatter: unformatted source is
still correct source. basedpyright here is a correctness proof, and a silent pass is the
exact failure DTO-08 exists to prevent. So the ``skipif`` below exists only for a
contributor who installed without the dev group, and
:func:`test_the_type_check_cannot_quietly_vanish_from_a_dev_environment` -- which carries no
skip marker -- fails outright if the dev group is present and basedpyright is not. ``prek
run --all-files`` already runs basedpyright over ``src`` and ``tests``, so its presence in
the pipeline is established independently.

**Which configuration this runs under.** A dedicated ``pyrightconfig.json`` is written
beside the file under analysis: ``typeCheckingMode = "strict"`` and no rule suppressions at
all. That makes the claim literally *"passes stock strict"* rather than
*"passes under Semolina's configuration"*, which disables seven ``report*`` rules
(``reportPrivateUsage``, ``reportIncompatibleMethodOverride``, ``reportUnknownMemberType``,
``reportUnknownVariableType``, ``reportUnknownArgumentType``, ``reportUnknownLambdaType``,
``reportMissingTypeStubs``, ``reportUnknownParameterType``). ``50-RESEARCH.md`` R-02 calls
this option (b) and makes it conditional on the generated DTO importing nothing but
``pydantic``, ``decimal``, ``datetime`` and ``typing`` (assumption A3) --
:meth:`TestTheGeneratedDtoPassesStockStrict.test_the_generated_module_imports_only_the_strict_configs_reach`
turns that condition into a test, so the day it stops holding is a failure and not a
silently weakened claim.

Two basedpyright subprocesses run here, roughly half a second of analysis each. The reports
are built once by module-scoped fixtures and asserted on by several tests, because the cost
is the subprocess and not the assertion.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pyarrow
import pytest

from semolina import Dimension, Fact, Metric, SemanticView
from semolina.codegen.dto_renderer import ProbedQuery, render_and_format_dtos
from semolina.codegen.probe import ROUTE_EXECUTE_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


def basedpyright_available() -> bool:
    """
    Report whether basedpyright can be invoked in the current environment.

    Mirrors :func:`semolina.codegen.python_renderer.ruff_available` exactly -- same
    ``importlib.util.find_spec`` idiom, same ``sys.executable -m <tool>`` invocation shape
    downstream. The *consequence* of a False answer differs, and the module docstring says
    why: ruff's absence degrades output, basedpyright's absence would degrade a proof.

    Returns:
        True if the ``basedpyright`` package is importable, False otherwise.
    """
    return importlib.util.find_spec("basedpyright") is not None


_DEV_GROUP_MARKERS = ("syrupy", "pytest_cov")
"""
Packages that appear in the ``dev`` dependency group and nowhere else.

Neither is needed to *run* this module, which is the point: they answer "was the dev group
installed?" without being confusable with "is the test suite running at all". ``pytest``
itself cannot serve, since it is present by construction whenever this file executes.
"""

_STRICT_REQUIRES_DEV_GROUP = "basedpyright ships in the dev dependency group, which is absent here"

_ALLOWED_GENERATED_IMPORTS = frozenset({"__future__", "datetime", "decimal", "typing", "pydantic"})
"""
The only top-level modules a generated DTO may import.

``50-RESEARCH.md`` assumption A3. The dedicated strict config resolves stubs for exactly
these; an import outside the set (``pyarrow``, say, which ships no stubs) would make the
config fail for a reason that has nothing to do with the generated code's quality, and the
documented fallback is to inherit the project config instead. Asserted rather than assumed,
so the fallback is triggered by a failing test rather than by a reader noticing.
"""


class TypeCheckSales(SemanticView, view="dto_typecheck_sales"):
    """
    A four-field model chosen to exercise the whole import set of a generated DTO.

    ``revenue`` maps to ``decimal.Decimal | None`` (metric nullability, D-09), ``country``
    to ``str``, ``ordered_at`` to ``datetime.datetime``, and ``origin`` -- probed as an
    Arrow ``struct``, which has no clean Python equivalent -- to ``Any`` plus a ``TODO``
    comment. So one render covers ``decimal``, ``datetime``, ``typing`` and ``pydantic``:
    every module A3 permits, none it does not.
    """

    revenue = Metric[int]()
    country = Dimension[str]()
    ordered_at = Fact[str]()
    origin = Fact[str]()


def _probed_snowflake_query() -> ProbedQuery:
    """
    Build a ``ProbedQuery`` for :class:`TypeCheckSales` from a hand-written schema.

    Snowflake rather than DuckDB deliberately: its metric result column is
    ``AGG("REVENUE")``, so the generated source carries a ``validation_alias`` containing
    double quotes. A file that type-checks proves the quoting survived into valid Python as
    well as into a passing string comparison.

    Returns:
        The record ``render_and_format_dtos`` takes, with no warehouse in the loop -- every
        dialect method the renderer calls is pure, so the probed schema was the only input
        that needed a connection.
    """
    from semolina.engines import sql

    query = (
        TypeCheckSales.query()
        .metrics(TypeCheckSales.revenue)
        .dimensions(TypeCheckSales.country, TypeCheckSales.ordered_at, TypeCheckSales.origin)
    )
    schema = pyarrow.schema(
        [
            pyarrow.field('AGG("REVENUE")', pyarrow.decimal128(38, 2)),
            pyarrow.field("COUNTRY", pyarrow.string()),
            pyarrow.field("ORDERED_AT", pyarrow.timestamp("us")),
            pyarrow.field("ORIGIN", pyarrow.struct([pyarrow.field("iso", pyarrow.string())])),
        ]
    )
    return ProbedQuery(
        class_name="RevenueByCountry",
        dotted_path="myapp.queries.revenue_by_country",
        query=query,
        dialect=sql.SnowflakeDialect(),
        schema=schema,
        route=ROUTE_EXECUTE_SCHEMA,
    )


def _type_check(workdir: Path, files: Mapping[str, str], target: str) -> dict[str, Any]:
    """
    Type-check one file under a dedicated stock-strict configuration.

    Writes every entry of ``files`` into ``workdir``, writes a ``pyrightconfig.json`` beside
    them carrying ``typeCheckingMode = "strict"`` and no rule suppressions, and analyses
    ``target``. ``--project`` points at that config while ``--pythonpath`` points at the
    interpreter running the tests, which is what lets an import of ``semolina`` resolve from
    the venv without inheriting the venv's project configuration along with it.

    There is deliberately no ``FileNotFoundError`` guard and no broad ``except``, unlike
    :func:`semolina.codegen.python_renderer.format_with_ruff`. That function degrades to
    unformatted source because unformatted source is still correct; this one has nothing
    safe to degrade to. Anything other than a JSON report on stdout raises, because the one
    outcome this harness must never produce is a green result it did not measure.

    Args:
        workdir: A directory to write the sources and the config into.
        files: Filename -> source text, all written into ``workdir``.
        target: The key of ``files`` to analyse. Only this file is analysed; the others are
            there to be imported.

    Returns:
        basedpyright's parsed JSON report, carrying ``summary.errorCount`` and
        ``generalDiagnostics``.

    Raises:
        AssertionError: If basedpyright produced no parseable JSON report, with its stdout
            and stderr attached.
    """
    for name, text in files.items():
        (workdir / name).write_text(text, encoding="utf-8")

    config = workdir / "pyrightconfig.json"
    config.write_text(
        json.dumps(
            {
                "typeCheckingMode": "strict",
                "pythonVersion": "3.11",
                # So a snippet can import the generated module sitting beside it. The
                # generated file's real home is a user's own package; `extraPaths` is how a
                # temp directory stands in for that without inventing a package layout.
                "extraPaths": [str(workdir)],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "basedpyright",
            "--outputjson",
            "--level",
            "error",
            "--project",
            str(config),
            "--pythonpath",
            sys.executable,
            str(workdir / target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    try:
        report: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        msg = (
            "basedpyright produced no JSON report, so nothing was measured.\n"
            f"returncode: {result.returncode}\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        raise AssertionError(msg) from exc
    return report


def _rules(report: dict[str, Any]) -> list[str]:
    """
    List the rule names basedpyright reported, in diagnostic order.

    Args:
        report: A parsed basedpyright JSON report.

    Returns:
        One rule name per diagnostic. A diagnostic with no ``rule`` key (a syntax error, for
        instance) contributes an empty string rather than being dropped, so a count taken
        from this list still matches ``generalDiagnostics``.
    """
    diagnostics: list[dict[str, Any]] = report["generalDiagnostics"]
    return [str(d.get("rule", "")) for d in diagnostics]


def _imported_modules(source: str) -> set[str]:
    """
    Name the top-level modules a source string imports, by parsing it.

    Args:
        source: Python source.

    Returns:
        Top-level module names, e.g. ``{'decimal', 'pydantic'}`` for
        ``import decimal.x`` and ``from pydantic import BaseModel``.
    """
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module.split(".")[0])
    return modules


_NON_STRICT_CONTROL = '''\
"""A module that stock strict must reject."""


def add(a, b: int) -> int:
    """Add two numbers, one of them unannotated."""
    return a + b
'''
"""
The negative control from ``50-RESEARCH.md`` R-02.

Trips ``reportMissingParameterType`` on the unannotated ``a`` and, because ``a``'s type is
unknown, ``reportUnknownVariableType`` on the return. The second rule is the discriminator:
``pyproject.toml`` disables it, so a report containing it cannot have come from Semolina's
configuration.
"""


@pytest.fixture(scope="module")
def generated_source() -> str:
    """
    Render the DTO under test once, through the renderer's own public entry point.

    Returns:
        Formatted generated source -- ``render_and_format_dtos``, so what is type-checked is
        the file the CLI would write rather than an unformatted intermediate.
    """
    return render_and_format_dtos([_probed_snowflake_query()], backend_label="snowflake")


@pytest.fixture(scope="module")
def strict_report(
    tmp_path_factory: pytest.TempPathFactory, generated_source: str
) -> dict[str, Any]:
    """
    Type-check the generated DTO on its own under stock strict.

    Args:
        tmp_path_factory: pytest's module-scoped temp directory factory.
        generated_source: The rendered DTO source.

    Returns:
        basedpyright's report.
    """
    workdir = tmp_path_factory.mktemp("dto_strict")
    return _type_check(workdir, {"generated_dto.py": generated_source}, "generated_dto.py")


@pytest.fixture(scope="module")
def control_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """
    Type-check the deliberately non-strict control through the same runner.

    Args:
        tmp_path_factory: pytest's module-scoped temp directory factory.

    Returns:
        basedpyright's report, which must not be clean.
    """
    workdir = tmp_path_factory.mktemp("dto_control")
    return _type_check(workdir, {"nonstrict.py": _NON_STRICT_CONTROL}, "nonstrict.py")


def test_the_type_check_cannot_quietly_vanish_from_a_dev_environment() -> None:
    """
    Fail loudly if the dev group is installed and basedpyright somehow is not.

    Every other test in this module is guarded by ``skipif``, which is right for a
    contributor who installed without the dev group and catastrophic if the tool ever
    disappears from the environment that is supposed to have it -- the module would report
    all-skipped, which reads as green. This test carries no marker, so that scenario is a
    failure instead of a silence.
    """
    if not all(importlib.util.find_spec(name) is not None for name in _DEV_GROUP_MARKERS):
        pytest.skip(f"none of {_DEV_GROUP_MARKERS} present, so the dev group is genuinely absent")
    assert basedpyright_available(), (
        f"{_DEV_GROUP_MARKERS} are installed, so the dev group is present, but basedpyright "
        "is not importable. DTO-08's proof would silently skip. Reinstall with "
        "`uv sync` rather than suppressing this."
    )


@pytest.mark.skipif(not basedpyright_available(), reason=_STRICT_REQUIRES_DEV_GROUP)
class TestTheGeneratedDtoPassesStockStrict:
    """The renderer's own output, analysed under strict with no rule suppressions."""

    def test_the_generated_dto_reports_zero_errors(self, strict_report: dict[str, Any]) -> None:
        """The whole of DTO-08's first half, measured by error count rather than exit code."""
        assert strict_report["summary"]["errorCount"] == 0, strict_report["generalDiagnostics"]

    def test_the_generated_source_carries_no_suppression_comment(
        self, generated_source: str
    ) -> None:
        """
        A suppressed error is invisible to the type checker, so the source is asked instead.

        This is a separate assertion from the error count on purpose. A file whose every
        diagnostic is silenced by a comment reports ``errorCount: 0`` and exits 0, so the
        type check alone cannot distinguish "well typed" from "quiet".
        """
        assert "type: ignore" not in generated_source
        assert "pyright: ignore" not in generated_source

    def test_the_generated_module_imports_only_the_strict_configs_reach(
        self, generated_source: str
    ) -> None:
        """
        Assumption A3 as a test: an import outside this set invalidates the strict config.

        The dedicated configuration resolves stubs for ``pydantic``, ``decimal``,
        ``datetime`` and ``typing`` and nothing else. Should the renderer ever emit an
        import beyond them -- ``pyarrow``, which ships no stubs, is the realistic one -- the
        documented fallback is to inherit the project config and record the downgrade. This
        assertion is what makes that a decision someone takes rather than a claim that
        quietly weakens.
        """
        assert _imported_modules(generated_source) <= _ALLOWED_GENERATED_IMPORTS

    def test_the_render_covers_every_module_the_strict_config_permits(
        self, generated_source: str
    ) -> None:
        """
        The measured render is the widest one, not a convenient one.

        Zero errors over a DTO that imports only ``pydantic`` would say little about the
        ``decimal``, ``datetime`` and ``Any`` channels. This model exercises all four, so
        the passing report above covers the renderer's whole annotation surface.
        """
        assert _imported_modules(generated_source) == _ALLOWED_GENERATED_IMPORTS


@pytest.mark.skipif(not basedpyright_available(), reason=_STRICT_REQUIRES_DEV_GROUP)
class TestTheTypeCheckHarnessCanFail:
    """The negative control: a runner that cannot fail proves nothing when it passes."""

    def test_a_deliberately_unannotated_function_is_caught(
        self, control_report: dict[str, Any]
    ) -> None:
        """
        A broken invocation would report zero errors forever and read as success.

        ``50-RESEARCH.md`` R-02's own control, so the expected rule is a measured value
        rather than a guessed one.
        """
        assert control_report["summary"]["errorCount"] > 0
        assert "reportMissingParameterType" in _rules(control_report)

    def test_the_dedicated_strict_config_is_the_one_in_effect(
        self, control_report: dict[str, Any]
    ) -> None:
        """
        Prove the analysis ran under stock strict rather than under Semolina's config.

        ``pyproject.toml`` sets ``reportUnknownVariableType = false``. basedpyright resolves
        configuration from the working directory unless ``--project`` overrides it, and
        pytest's working directory *is* the repo root -- so without the override this
        diagnostic would be absent. Its presence is what separates "passes stock strict"
        from "passes under a configuration that disables seven rules".
        """
        assert "reportUnknownVariableType" in _rules(control_report)
