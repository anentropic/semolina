"""
Structural enforcement of the asyncio-and-Trio loop matrix (ASYNC-05, D-17).

ASYNC-05 requires the async tests green under **both** asyncio and Trio, and
D-17 fixes the mechanism: a module-level ``pytestmark = pytest.mark.anyio`` plus
a module-local ``anyio_backend`` fixture parametrized over both backend names.
Running the suite proves today's modules are parametrized. It proves nothing
about tomorrow's: a new async test module that omits the fixture runs on asyncio
alone and still goes green, so the matrix quietly shrinks and the suite reports
success either way. This module makes that omission a build failure.

The check reads source rather than importing test modules. Importing a test
module from inside a test invites collection-order and fixture side effects, and
none of the two properties being checked need a live object to observe — both are
plainly visible in the parsed tree.

Selection is by content, never by filename. ``test_async_packaging.py`` and this
module both carry the ``test_async``-ish name prefix while defining no async
test, so a name glob would either flag them wrongly or need a hand-maintained
exclusion list that rots as modules come and go. A module that defines no async
test is simply not in scope, and by that rule this module is not in scope either
— it needs neither the anyio marker nor the backend fixture.

One timing caveat: run while a sibling plan in the same wave has not yet landed
its async test module, this check simply does not see that module yet. That is
not a hole. The phase gate re-runs the full suite once every plan has landed,
which is where the complete set is checked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

TESTS_ROOT = Path(__file__).resolve().parents[1]

#: The two loop backends D-17 requires every async test module to cover.
REQUIRED_BACKENDS = frozenset({"asyncio", "trio"})

#: pytest's own test-function prefix, which is what makes a coroutine a test.
TEST_PREFIX = "test_"

#: The marker that hands a coroutine test to anyio's runner.
ANYIO_MARKER = "anyio"

#: The fixture name anyio's pytest plugin reads the backend from.
BACKEND_FIXTURE = "anyio_backend"


def _defines_async_test(tree: ast.Module) -> bool:
    """
    Report whether a parsed module defines at least one async test function.

    Walks the whole tree rather than only the module body, so a coroutine test
    inside a test class counts exactly as much as a module-level one.

    Args:
        tree: Parsed module to inspect.

    Returns:
        True if any ``async def`` in the module is named like a pytest test.
    """
    return any(
        isinstance(node, ast.AsyncFunctionDef) and node.name.startswith(TEST_PREFIX)
        for node in ast.walk(tree)
    )


def _attribute_names(value: ast.expr) -> set[str]:
    """
    Collect every attribute name appearing anywhere in an expression.

    Used to recognize the anyio marker without pinning how it was spelled:
    ``pytest.mark.anyio`` and ``[pytest.mark.anyio, pytest.mark.unit]`` both
    yield ``anyio`` here.

    Args:
        value: Expression node to scan.

    Returns:
        Set of attribute names found in the expression.
    """
    return {node.attr for node in ast.walk(value) if isinstance(node, ast.Attribute)}


def _string_constants(value: ast.expr) -> set[str]:
    """
    Collect every string literal appearing anywhere in an expression.

    Args:
        value: Expression node to scan.

    Returns:
        Set of string constant values found in the expression.
    """
    return {
        node.value
        for node in ast.walk(value)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _dotted_name(node: ast.expr) -> str:
    """
    Render a dotted attribute/name expression back to source-like text.

    Args:
        node: Expression node, typically a decorator callee.

    Returns:
        Dotted string such as ``pytest.fixture``, or the empty string for an
        expression that is not a plain dotted name.
    """
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    parts.append(current.id)
    return ".".join(reversed(parts))


def _has_anyio_pytestmark(tree: ast.Module) -> bool:
    """
    Report whether the module assigns a module-level ``pytestmark`` naming anyio.

    Args:
        tree: Parsed module to inspect.

    Returns:
        True if a top-level ``pytestmark`` assignment references the anyio
        marker.
    """
    for node in tree.body:
        if isinstance(node, ast.Assign):
            named = any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in node.targets
            )
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            named = isinstance(node.target, ast.Name) and node.target.id == "pytestmark"
            value = node.value
        else:
            continue
        if named and ANYIO_MARKER in _attribute_names(value):
            return True
    return False


def _has_both_backends_fixture(tree: ast.Module) -> bool:
    """
    Report whether the module defines a both-backends ``anyio_backend`` fixture.

    The fixture must be module-level, decorated with a fixture decorator called
    with arguments, and carry a ``params`` argument whose literal collection
    names both backends.

    Args:
        tree: Parsed module to inspect.

    Returns:
        True if such a fixture is defined at module level.
    """
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name != BACKEND_FIXTURE:
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not _dotted_name(decorator.func).endswith("fixture"):
                continue
            for keyword in decorator.keywords:
                if keyword.arg != "params":
                    continue
                if REQUIRED_BACKENDS.issubset(_string_constants(keyword.value)):
                    return True
    return False


def _async_test_modules() -> list[tuple[Path, ast.Module]]:
    """
    Find every module under ``tests/`` that defines at least one async test.

    Returns:
        Sorted list of ``(path, parsed module)`` pairs, one per in-scope module.
    """
    found: list[tuple[Path, ast.Module]] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _defines_async_test(tree):
            found.append((path, tree))
    return found


class TestLoopMatrixIsEnforcedStructurally:
    """Every async test module must carry the anyio marker and both backends."""

    def test_every_async_test_module_covers_asyncio_and_trio(self) -> None:
        """
        Each module defining an async test declares the marker and both backends.

        The failure message names the offending file and states which of the two
        requirements is missing, because a bare assertion error here would send a
        future reader hunting through the AST helpers to work out what tripped.
        """
        modules = _async_test_modules()
        failures: list[str] = []
        for path, tree in modules:
            missing: list[str] = []
            if not _has_anyio_pytestmark(tree):
                missing.append(
                    "a module-level `pytestmark` referencing the anyio marker "
                    "(`pytestmark = pytest.mark.anyio`)"
                )
            if not _has_both_backends_fixture(tree):
                missing.append(
                    "a module-level `anyio_backend` fixture parametrized over "
                    "both backends (`@pytest.fixture(params=['asyncio', 'trio'])`)"
                )
            if missing:
                relative = path.relative_to(TESTS_ROOT.parent)
                failures.append(f"  {relative} is missing " + "; and ".join(missing))

        assert not failures, (
            "ASYNC-05 (D-17) requires every test module defining an async test to run "
            "under both asyncio and Trio. These modules would silently cover asyncio "
            "only:\n" + "\n".join(failures)
        )

    def test_discovery_is_not_vacuous(self) -> None:
        """
        The walk selects at least one module, so an empty walk cannot pass.

        A checker that greens because it found nothing is worse than no checker,
        and this module's whole purpose is to not be that one.
        """
        modules = _async_test_modules()
        assert modules, (
            f"No module under {TESTS_ROOT} defines an async test, so the loop-matrix "
            "invariant checked nothing. Either the async test suite has gone missing "
            "or this discovery walk is broken."
        )

    def test_modules_without_async_tests_are_out_of_scope(self) -> None:
        """
        Selection is by content, so async-free modules escape the invariant.

        Named here rather than left implicit: the packaging module and this
        checker both read as async-adjacent by filename while defining no async
        test, and they are the reason selection is by content and not by glob.
        """
        selected = {path for path, _ in _async_test_modules()}

        assert Path(__file__).resolve() not in selected
        assert (TESTS_ROOT / "unit" / "test_async_packaging.py").resolve() not in selected
