"""
Packaging contract for the optional async surface (ASYNC-04).

Two things are asserted here, and they fail for different reasons:

- The declaration half reads ``pyproject.toml`` and checks that the ``[async]``
  extra exists, pins ``adbc-poolhouse[async]>=1.6.2``, is reachable through the
  ``all`` extra (every CI test job syncs with ``--extra all``), that the base
  dependency floor agrees, and that ``trio`` is in the dev group.
- The lazy-import half checks that ``import semolina`` does not drag ``anyio``
  in. That must hold for a plain ``pip install semolina``, but anyio *is*
  installed in this dev venv, so the check runs in a child interpreter and looks
  at that process's ``sys.modules`` rather than this one's.

Two defects set the floor, and both floors move together so a sync install and an
async install never resolve to different poolhouse builds.

It is not 1.5.0, the version the requirement originally named: ``_resolve_tuning``,
which makes ``create_async_pool`` honour the config's own ``pool_size``, landed in
adbc-poolhouse 1.6.0.

It is not 1.6.1 either: that release's cancel path ran poison-recovery without
waiting for the aborted worker thread to unwind, which wedges the DuckDB driver
permanently. Since the offload runs ``abandon_on_cancel=False`` the awaiting task
never completed and no enclosing timeout could rescue it. Fixed in 1.6.2
(anentropic/adbc-poolhouse#43); ASYNC-06 cannot hold below it.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

ASYNC_PIN = "adbc-poolhouse[async]>=1.6.2"
BASE_PIN = "adbc-poolhouse>=1.6.2"


def _pyproject() -> dict[str, Any]:
    """Parse the project's own pyproject.toml."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def test_packaging_base_dependency_pins_poolhouse_floor() -> None:
    """The base dependency floor names >=1.6.2, matching the async extra."""
    deps = _pyproject()["project"]["dependencies"]
    assert BASE_PIN in deps, deps


def test_packaging_declares_async_extra() -> None:
    """The [async] extra exists and pins adbc-poolhouse[async]>=1.6.2 exactly."""
    extras = _pyproject()["project"]["optional-dependencies"]
    assert "async" in extras, sorted(extras)
    assert extras["async"] == [ASYNC_PIN], extras["async"]


def test_packaging_all_extra_includes_async() -> None:
    """
    The ``all`` extra reaches ``async``.

    CI's four test jobs sync with ``--extra all``; leaving async out would mean
    the async tests never run there while passing locally.
    """
    extras = _pyproject()["project"]["optional-dependencies"]
    assert any("async" in requirement for requirement in extras["all"]), extras["all"]


def test_packaging_dev_group_pins_trio() -> None:
    """
    The dev group carries trio for the Trio half of the loop matrix.

    ``adbc-poolhouse[async]`` declares only ``anyio>=4.13``, and anyio does not
    vendor Trio, so the ``all`` extra alone leaves it missing.
    """
    dev = _pyproject()["dependency-groups"]["dev"]
    assert any(requirement.startswith("trio") for requirement in dev), dev


def test_packaging_importing_semolina_does_not_import_anyio() -> None:
    """
    ``import semolina`` leaves anyio unimported, so a base install stays clean.

    adbc-poolhouse resolves its async entry points lazily (PEP 562) precisely to
    keep the sync path anyio-free; a module-level ``from adbc_poolhouse import
    create_async_pool`` in Semolina would defeat that. anyio is installed in this
    venv, so the observation has to happen in a child interpreter.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import semolina, sys; print('anyio' in sys.modules)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", (
        f"importing semolina pulled anyio into sys.modules: {result.stdout!r}"
    )
