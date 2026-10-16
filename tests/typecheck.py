"""
Run basedpyright over source written to a temp directory, for tests that prove typing claims.

Shared by the generated-DTO type check and the builder's negative typing tests. Both need
the same thing: a stock-strict configuration that is not Semolina's own (which disables
several rules), an import of ``semolina`` resolved from the test interpreter's venv, and a
harness that raises rather than reading green when basedpyright produced no report.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

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


DEV_GROUP_MARKERS = ("syrupy", "pytest_cov")
"""
Packages that appear in the ``dev`` dependency group and nowhere else.

Neither is needed to *run* the type-check tests, which is the point: they answer "was the dev group
installed?" without being confusable with "is the test suite running at all". ``pytest``
itself cannot serve, since it is present by construction whenever this file executes.
"""

STRICT_REQUIRES_DEV_GROUP = "basedpyright ships in the dev dependency group, which is absent here"


def type_check(workdir: Path, files: Mapping[str, str], target: str) -> dict[str, Any]:
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


def rules(report: dict[str, Any]) -> list[str]:
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
