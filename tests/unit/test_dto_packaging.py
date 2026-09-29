"""
Packaging contract for the optional Arrow/dataframe/DTO surface.

Two kinds of claim are asserted here:

- **Composition rules** between extras, read from ``pyproject.toml``. Each one is a rule a
  careless edit could break and nothing else would notice, because every CI test job syncs
  with ``--extra all``: an extra that advertises ``fetch_df()`` or ``.into()`` must also
  bring pyarrow, and ``all`` must reach every result extra. The version floors themselves are
  deliberately not restated here; ``pyproject.toml`` is their one home, with the reasoning
  beside each.
- **Lazy imports**: ``import semolina`` must not import the optional packages. They *are*
  installed in this dev venv, so the check runs in a child interpreter and looks at that
  process's ``sys.modules``.

Neither half can prove what a *default install* contains — a test can only observe the venv
it runs in, and this one has everything. That claim belongs to CI's ``packaging-smoke`` job,
which builds a real extras-free venv and asserts absence against it. A module-level import of
an optional package anywhere in ``src/`` is refused by ruff's TID253 rule before either runs.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

PYARROW_EXTRA_REFERENCE = "semolina[pyarrow]"
"""How an extra reaches pyarrow: through the one extra that pins it, never a second pin."""

OPTIONAL_PACKAGES = ("pyarrow", "pandas", "polars", "arrowmodel")


def _extras() -> dict[str, list[str]]:
    """Return the declared optional-dependency table."""
    with PYPROJECT.open("rb") as fh:
        pyproject: dict[str, Any] = tomllib.load(fh)
    return pyproject["project"]["optional-dependencies"]


@pytest.mark.parametrize("extra", ["pandas", "arrowmodel", "duckdb", "snowflake", "databricks"])
def test_packaging_extra_reaches_pyarrow_through_the_pyarrow_extra(extra: str) -> None:
    """
    Every backend extra, ``[pandas]`` and ``[arrowmodel]`` bring pyarrow, via ``semolina[pyarrow]``.

    Each needs pyarrow at runtime. ADBC reads every row through a pyarrow reader, so a
    backend extra without it could run a query and then read nothing back but
    ``fetch_polars()``. ``fetch_df()`` is ADBC's ``self.reader.read_pandas()``, and the
    ``reader`` property requires pyarrow before pandas is touched; both DTO methods call
    ``_require("pyarrow", ...)`` before ``_require("arrowmodel", ...)``. An extra that stopped
    at its own package would advertise the feature and then raise
    ``SemolinaMissingDependencyError`` on the first call.

    Reached through the self-reference rather than a second ``pyarrow>=`` pin, because two
    copies of a floor drift apart silently.
    """
    requirements = _extras()[extra]

    assert PYARROW_EXTRA_REFERENCE in requirements, requirements
    assert not any(requirement.startswith("pyarrow") for requirement in requirements), requirements


def test_packaging_polars_extra_deliberately_does_not_reach_pyarrow() -> None:
    """
    ``[polars]`` must NOT compose ``semolina[pyarrow]`` — the asymmetry is deliberate.

    ``fetch_polars`` is ``polars.from_arrow(self.fetch_arrow())``, and ``fetch_arrow()``
    returns the raw stream handle without constructing a reader, so it never reaches ADBC's
    pyarrow guard. Semolina's ``fetch_polars`` guard is correspondingly polars-only.

    Pinned because it looks like an inconsistency: a "make the extras consistent" tidy-up
    would add a dependency a working install does not need.
    """
    polars_extra = _extras()["polars"]

    assert PYARROW_EXTRA_REFERENCE not in polars_extra, polars_extra
    assert not any(requirement.startswith("pyarrow") for requirement in polars_extra), polars_extra


def test_packaging_all_extra_includes_every_result_extra() -> None:
    """
    The ``all`` extra reaches all four result extras.

    CI's test jobs sync with ``--extra all``; leaving one out would mean the tests for that
    surface never run there while passing locally.
    """
    all_requirements = _extras()["all"]

    for package in OPTIONAL_PACKAGES:
        assert any(package in requirement for requirement in all_requirements), (
            f"{package} unreachable through the all extra: {all_requirements}"
        )


def _imported_after_import_semolina(module: str) -> bool:
    """
    Report whether ``import semolina`` leaves ``module`` in a fresh interpreter's modules.

    Args:
        module: A dotted module name.

    Returns:
        True if the child interpreter had imported it.
    """
    result = subprocess.run(
        [sys.executable, "-c", f"import semolina, sys; print({module!r} in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip() == "True"


def test_packaging_importing_semolina_does_not_import_arrowmodel() -> None:
    """
    ``import semolina`` leaves arrowmodel unimported.

    ``.into()`` and ``iter_into()`` resolve arrowmodel inside the method body, behind a
    ``find_spec`` guard, so a base install stays clean.

    Only arrowmodel is checked this way, and the exclusions are measured rather than
    assumed. ``pyarrow``, ``pandas`` and ``polars`` are all in ``sys.modules`` after
    ``import semolina`` in this venv, and none of them arrives through Semolina: the chain is
    ``semolina.config`` -> ``adbc_poolhouse`` -> ``adbc_driver_manager.dbapi``, which imports
    them opportunistically. Asserting them absent *here* would be a red test with no defect
    behind it; ruff's TID253 and CI's base-install job cover them instead.
    """
    assert not _imported_after_import_semolina("arrowmodel")


def test_packaging_importing_semolina_leaves_codegen_unimported() -> None:
    """
    ``import semolina`` does not execute ``codegen.arrow_map``.

    ``arrow_map`` is the one module exempt from ruff's optional-import ban, because it
    imports pyarrow at module scope. The exemption is only safe while the package root never
    reaches it: re-exporting a codegen symbol from ``semolina/__init__.py`` would quietly
    make pyarrow a hard dependency.
    """
    assert not _imported_after_import_semolina("semolina.codegen.arrow_map")
