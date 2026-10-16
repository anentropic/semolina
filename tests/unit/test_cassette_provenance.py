"""
Copied cassettes are marked as copied (TEST-02).

Only ``test_queries`` and ``test_introspect`` record against a warehouse. Every other
cassette was copied byte for byte from one of their recordings, so a reader seeing it pass
learns only that the SQL still matches a recording, not that anything was run live. Such a
test and its cassette carry ``copied`` in their name, so the test id says so wherever it is
reported. The marking is checked here because a new copied cassette would otherwise look
exactly like a recorded one.

A node-id cassette's directory is named after its test, so checking the directory checks the
test. A named cassette (``@pytest.mark.adbc_cassette("<name>")``) is not, so the tests that
use one are found by reading the integration modules and checked by their own names.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"
CASSETTES = INTEGRATION / "cassettes"

RECORDED_MODULES = ("test_queries/", "test_introspect/")
"""The integration modules that record their own cassettes."""


def _cassette_names() -> list[str]:
    """
    Name each cassette by the path segment that its test chose.

    A node-id cassette lives at ``integration/<module>/<test>/``, a named one at
    ``<name>/``.

    Returns:
        ``<module>/<test>`` for node-id cassettes and ``<name>`` for named ones, sorted.
    """
    names: list[str] = []
    for entry in sorted(CASSETTES.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == "integration":
            names.extend(
                f"{module.name}/{test.name}"
                for module in sorted(entry.iterdir())
                if module.is_dir()
                for test in sorted(module.iterdir())
                if test.is_dir()
            )
        else:
            names.append(entry.name)
    return names


CASSETTE_NAMES = _cassette_names()


def test_the_scan_finds_recorded_and_copied_cassettes() -> None:
    """The scan is not vacuous: it sees both kinds."""
    assert any(name.startswith("test_queries/") for name in CASSETTE_NAMES)
    assert any(not name.startswith(RECORDED_MODULES) for name in CASSETTE_NAMES)


@pytest.mark.parametrize("name", [n for n in CASSETTE_NAMES if not n.startswith(RECORDED_MODULES)])
def test_a_cassette_outside_the_recording_modules_is_marked_copied(name: str) -> None:
    """A cassette no recording module owns says ``copied`` in its name."""
    assert "copied" in name


def _named_cassette_tests(source: str) -> list[str]:
    """
    Find the tests in a module that carry a named cassette.

    Args:
        source: The module's source.

    Returns:
        The names of functions decorated with a call to ``adbc_cassette``, in order.
    """
    tests: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "adbc_cassette"
            ):
                tests.append(node.name)
    return tests


NAMED_CASSETTE_TESTS = [
    f"{module.stem}::{test}"
    for module in sorted(INTEGRATION.glob("test_*.py"))
    if f"{module.stem}/" not in RECORDED_MODULES
    for test in _named_cassette_tests(module.read_text())
]


def test_the_module_scan_finds_named_cassette_tests() -> None:
    """The module scan is not vacuous: it finds a decorated test, sync or async."""
    source = (
        "import pytest\n"
        "@pytest.mark.adbc_cassette('x_copied')\n"
        "async def test_unmarked(): ...\n"
        "@pytest.mark.adbc_cassette('y_copied')\n"
        "def test_also_unmarked(): ...\n"
        "def test_plain(): ...\n"
    )
    assert _named_cassette_tests(source) == ["test_unmarked", "test_also_unmarked"]
    assert NAMED_CASSETTE_TESTS


@pytest.mark.parametrize("test", NAMED_CASSETTE_TESTS)
def test_a_named_cassette_test_outside_the_recording_modules_is_marked_copied(test: str) -> None:
    """A test replaying a named cassette says ``copied`` in its own name, too."""
    assert "copied" in test.split("::")[1]
