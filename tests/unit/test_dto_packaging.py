"""
Packaging contract for the optional Arrow/dataframe/DTO surface (DTO-05).

Two things are asserted here, and they fail for different reasons:

- The declaration half reads ``pyproject.toml`` and checks that each of the four
  extras Phase 49 published — ``[pyarrow]``, ``[pandas]``, ``[polars]``,
  ``[arrowmodel]`` — exists with exactly the pin it was given, that ``all``
  reaches all four (every CI test job syncs with ``--extra all``), and that
  ``duckdb`` reaches pyarrow through ``semolina[pyarrow]`` instead of repeating
  the pin. Equality, not containment, so a silently loosened floor fails here.
- The lazy-import half checks that ``import semolina`` does not drag the
  optional packages in. That must hold for a plain ``pip install semolina``, but
  they *are* installed in this dev venv, so the check runs in a child
  interpreter and looks at that process's ``sys.modules`` rather than this one's.

Neither half can prove what a *default install* contains — a test can only
observe the venv it runs in, and this one has everything. That claim belongs to
CI's ``packaging-smoke`` job, which builds a real extras-free venv and asserts
absence against it.

The floors are justified in ``pyproject.toml`` beside each extra rather than
repeated here; two are worth restating because they are the ones a future edit
is most likely to get wrong. ``pandas>=2.0.0`` is conservative and unmeasured —
behaviour was exercised at 2.3.3 and 3.0.5, and 2.0.0 marks the major-version
boundary below which the nullable-dtype and Arrow-interop surface changes shape.
``arrowmodel>=1.0.0`` is a floor rather than an exact pin even though 1.0.0 is
currently the only release, so a future 1.1 can land in a user's environment
without forcing a Semolina release.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SRC = REPO_ROOT / "src" / "semolina"

PYARROW_PIN = "pyarrow>=17.0.0"
PANDAS_PIN = "pandas>=2.0.0"
POLARS_PIN = "polars>=1.0.0"
ARROWMODEL_PIN = "arrowmodel>=1.0.0"

DUCKDB_PYARROW_REFERENCE = "semolina[pyarrow]"

OPTIONAL_PACKAGES = ("pyarrow", "pandas", "polars", "arrowmodel")

# The one module in the package that may import an optional package at module scope.
# codegen runs behind the `semolina codegen` CLI entry point and is never reached by
# `import semolina`, which the companion test below asserts rather than assumes.
MODULE_SCOPE_IMPORT_ALLOWLIST = {"codegen/arrow_map.py"}


def _pyproject() -> dict[str, Any]:
    """Parse the project's own pyproject.toml."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _extras() -> dict[str, list[str]]:
    """Return the declared optional-dependency table."""
    return _pyproject()["project"]["optional-dependencies"]


def test_packaging_declares_pyarrow_extra() -> None:
    """The [pyarrow] extra exists and pins pyarrow>=17.0.0 exactly."""
    extras = _extras()
    assert "pyarrow" in extras, sorted(extras)
    assert extras["pyarrow"] == [PYARROW_PIN], extras["pyarrow"]


def test_packaging_declares_pandas_extra() -> None:
    """The [pandas] extra exists and pins pandas>=2.0.0 exactly."""
    extras = _extras()
    assert "pandas" in extras, sorted(extras)
    assert extras["pandas"] == [PANDAS_PIN], extras["pandas"]


def test_packaging_declares_polars_extra() -> None:
    """The [polars] extra exists and pins polars>=1.0.0 exactly."""
    extras = _extras()
    assert "polars" in extras, sorted(extras)
    assert extras["polars"] == [POLARS_PIN], extras["polars"]


def test_packaging_declares_arrowmodel_extra() -> None:
    """The [arrowmodel] extra exists and pins arrowmodel>=1.0.0 exactly."""
    extras = _extras()
    assert "arrowmodel" in extras, sorted(extras)
    assert extras["arrowmodel"] == [ARROWMODEL_PIN], extras["arrowmodel"]


def test_packaging_all_extra_includes_every_result_extra() -> None:
    """
    The ``all`` extra reaches all four result extras.

    CI's four test jobs sync with ``--extra all``; leaving one out would mean the
    tests for that surface never run there while passing locally.
    """
    all_requirements = _extras()["all"]

    for package in OPTIONAL_PACKAGES:
        assert any(package in requirement for requirement in all_requirements), (
            f"{package} unreachable through the all extra: {all_requirements}"
        )


def test_packaging_duckdb_extra_references_the_pyarrow_extra() -> None:
    """
    ``duckdb`` reaches pyarrow through ``semolina[pyarrow]``, not its own pin.

    Before Phase 49 the duckdb extra carried ``pyarrow>=17.0.0`` directly. Two
    copies of a floor drift apart silently; the self-reference means the pin has
    one home and moving it moves both.
    """
    duckdb = _extras()["duckdb"]

    assert DUCKDB_PYARROW_REFERENCE in duckdb, duckdb
    assert not any(requirement.startswith("pyarrow") for requirement in duckdb), duckdb


@pytest.mark.parametrize("module", ["arrowmodel"])
def test_packaging_importing_semolina_does_not_import(module: str) -> None:
    """
    ``import semolina`` leaves the optional package unimported.

    ``.into()`` and ``iter_into()`` resolve arrowmodel inside the method body,
    behind a ``find_spec`` guard, precisely so a base install stays clean; a
    module-level ``import arrowmodel`` in ``dto.py`` would defeat that. arrowmodel
    is installed in this venv, so the observation has to happen in a child
    interpreter.

    Only arrowmodel is parametrised, and the exclusions are measured rather than
    assumed. ``pyarrow``, ``pandas`` and ``polars`` are all in ``sys.modules``
    after ``import semolina`` in this venv, and none of them arrives through
    Semolina: the chain is ``semolina.config`` -> ``adbc_poolhouse`` ->
    ``adbc_driver_manager.dbapi``, which imports ``pyarrow`` and
    ``pyarrow.dataset`` (that one pulls pandas) unconditionally at module scope
    and imports ``polars`` in a ``try``/``except ImportError`` inside
    ``adbc_driver_manager._dbapi_backend``. adbc-driver-manager declares none of
    the three as dependencies, so a genuinely base install still lacks them and
    the ``_require`` guards stay reachable — but asserting them absent *here*
    would be a red test with no defect behind it. What that costs is covered by
    the module-scope import scan below, which catches a hoisted
    ``import polars`` in ``cursor.py`` that ``sys.modules`` no longer can.
    """
    result = subprocess.run(
        [sys.executable, "-c", f"import semolina, sys; print({module!r} in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", (
        f"importing semolina pulled {module} into sys.modules: {result.stdout!r}"
    )


def _module_scope_imports(tree: ast.Module) -> list[str]:
    """
    Collect the top-level names imported when the module body executes.

    ``if TYPE_CHECKING:`` blocks are skipped because their contents never run,
    which is exactly the escape hatch ``cursor.py`` uses to annotate a
    ``pyarrow.Table`` return type without importing pyarrow. Module-level
    ``try``/``except`` blocks are followed, since those imports do execute.
    """
    names: list[str] = []

    def visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.Import):
                names.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.append(node.module.split(".")[0])
            elif isinstance(node, ast.If):
                if "TYPE_CHECKING" not in ast.dump(node.test):
                    visit(node.body)
                    visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                for handler in node.handlers:
                    visit(handler.body)
                visit(node.orelse)
                visit(node.finalbody)

    visit(tree.body)
    return names


def test_packaging_no_module_scope_optional_imports() -> None:
    """
    No module under ``src/semolina`` imports an optional package at module scope.

    This is the guard the child-interpreter check can no longer provide for
    pyarrow, pandas and polars: all three are already in ``sys.modules`` by the
    time ``semolina/__init__.py`` finishes, dragged in by adbc-driver-manager,
    so a hoisted ``import polars`` in ``cursor.py`` would be invisible there. It
    is visible here, because this reads the source instead of the process.

    ``codegen/arrow_map.py`` is allowlisted: it maps Arrow types to Python
    annotations, so pyarrow is not optional to it, and it sits behind the
    ``semolina codegen`` CLI path rather than the package root.
    """
    offenders: dict[str, list[str]] = {}

    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC).as_posix()
        if relative in MODULE_SCOPE_IMPORT_ALLOWLIST:
            continue
        imported = _module_scope_imports(ast.parse(path.read_text(encoding="utf-8")))
        found = [name for name in imported if name in OPTIONAL_PACKAGES]
        if found:
            offenders[relative] = found

    assert not offenders, f"optional packages imported at module scope: {offenders}"


def test_packaging_importing_semolina_leaves_codegen_unimported() -> None:
    """
    The allowlisted module-scope pyarrow import is not reached by the package root.

    ``codegen/arrow_map.py`` is the single exemption above, and the exemption is
    only safe while ``import semolina`` does not execute it. Asserted rather than
    assumed, because re-exporting a codegen symbol from ``semolina/__init__.py``
    would quietly turn pyarrow into a hard dependency.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import semolina, sys; print('semolina.codegen.arrow_map' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", (
        f"importing semolina executed codegen.arrow_map: {result.stdout!r}"
    )
