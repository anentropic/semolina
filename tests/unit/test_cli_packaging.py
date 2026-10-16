"""
Packaging contract for the ``[cli]`` extra and a light ``import semolina``.

Three claims:

- **The CLI's dependencies are an extra.** ``typer``, ``rich``, ``jinja2`` and ``griffelib``
  are needed only by the ``semolina`` command, so they live in ``[cli]`` and a backend
  service that only queries does not install them. Read from ``pyproject.toml``.
- **``import semolina`` stays light.** It imports none of the CLI's packages, and not
  ``semolina.config`` either, which would bring pydantic-settings and SQLAlchemy.
  ``create_engine`` still resolves from the package root, on first use. All of these are
  installed in this dev venv, so the check runs in a child interpreter and looks at that
  process's ``sys.modules``.
- **The command explains itself without the extra.** The console script stays installed in
  a base install, so it must print the install hint rather than a traceback. The child
  interpreter blocks the CLI's packages through ``sys.modules`` to stand in for their
  absence; CI's ``packaging-smoke`` job makes the same claim against a real base install.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

CLI_PACKAGES = {"typer": "typer", "rich": "rich", "jinja2": "jinja2", "griffelib": "griffe"}
"""Each CLI dependency's distribution name, mapped to the module it installs."""


def _project() -> dict[str, Any]:
    """Return the ``[project]`` table."""
    with PYPROJECT.open("rb") as fh:
        pyproject: dict[str, Any] = tomllib.load(fh)
    return pyproject["project"]


def _names(requirements: list[str]) -> set[str]:
    """
    Reduce requirement strings to their distribution names.

    Args:
        requirements: Requirement strings such as ``"typer>=0.12.0"``.

    Returns:
        The names, lower-cased, with extras and version specifiers dropped.
    """
    import re

    return {re.split(r"[\[<>=!~ ;]", r, maxsplit=1)[0].lower() for r in requirements}


@pytest.mark.parametrize("distribution", list(CLI_PACKAGES))
def test_cli_dependency_is_not_a_base_dependency(distribution: str) -> None:
    """A plain ``pip install semolina`` does not install the CLI's packages."""
    assert distribution not in _names(_project()["dependencies"])


@pytest.mark.parametrize("distribution", list(CLI_PACKAGES))
def test_cli_extra_installs_the_cli_dependency(distribution: str) -> None:
    """``pip install semolina[cli]`` installs each of the CLI's packages."""
    assert distribution in _names(_project()["optional-dependencies"]["cli"])


def test_codegen_lint_extra_includes_cli() -> None:
    """``[codegen-lint]`` formats the command's output, so it brings the command too."""
    assert "semolina[cli]" in _project()["optional-dependencies"]["codegen-lint"]


def test_all_extra_includes_cli() -> None:
    """The ``all`` extra reaches ``cli``, so CI's ``--extra all`` runs the codegen suite."""
    all_requirements = _project()["optional-dependencies"]["all"]
    assert any("cli" in requirement for requirement in all_requirements), all_requirements


def _run(code: str) -> subprocess.CompletedProcess[str]:
    """
    Run ``code`` in a fresh interpreter.

    Args:
        code: Python source for ``-c``.

    Returns:
        The completed process, with text stdout and stderr.
    """
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)


@pytest.mark.parametrize(
    "module",
    [*CLI_PACKAGES.values(), "semolina.config", "pydantic_settings", "sqlalchemy"],
)
def test_importing_semolina_does_not_import(module: str) -> None:
    """``import semolina`` leaves ``module`` unimported."""
    result = _run(f"import semolina, sys; print({module!r} in sys.modules)")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


@pytest.mark.parametrize("name", ["create_engine", "create_async_engine"])
def test_engine_factories_still_resolve_from_the_package_root(name: str) -> None:
    """
    ``semolina.create_engine`` works after the lazy import, and is the config module's own.

    Checked in a child interpreter, so the first access really is the one that imports
    ``semolina.config``.
    """
    result = _run(
        "import sys, semolina\n"
        f"factory = semolina.{name}\n"
        "import semolina.config\n"
        f"assert factory is semolina.config.{name}\n"
        f"from semolina import {name}\n"
        "print('ok')"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_console_script_points_at_the_guarded_entry() -> None:
    """
    The ``semolina`` command starts in a module that imports none of the CLI's packages.

    Pointing it at ``semolina.cli:app`` would import typer before anything could explain
    that the extra is missing.
    """
    assert _project()["scripts"]["semolina"] == "semolina.__main__:main"


def _main_without(blocked: list[str], argv: list[str]) -> subprocess.CompletedProcess[str]:
    """
    Run the console script's entry point with some packages made unimportable.

    Args:
        blocked: Module names to block through ``sys.modules``, standing in for packages a
            base install does not have.
        argv: Arguments after the program name.

    Returns:
        The completed process.
    """
    return _run(
        "import sys\n"
        f"for name in {blocked!r}:\n"
        "    sys.modules[name] = None\n"
        f"sys.argv = ['semolina', *{argv!r}]\n"
        "from semolina.__main__ import main\n"
        "main()\n"
    )


@pytest.mark.parametrize("missing", list(CLI_PACKAGES.values()))
def test_command_without_the_extra_prints_the_install_hint(missing: str) -> None:
    """Any one CLI package missing gives the hint and exit 2, never a traceback."""
    result = _main_without([missing], ["codegen", "--help"])
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert 'pip install "semolina[cli]"' in result.stderr
    assert "Traceback" not in result.stderr


def test_command_with_the_extra_runs() -> None:
    """With every CLI package present, the same entry point runs the real CLI."""
    result = _main_without([], ["--help"])
    assert result.returncode == 0, result.stderr
    assert "codegen" in result.stdout
