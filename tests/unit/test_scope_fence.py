"""
A runnable gate on the value path ``47-DECISIONS.md`` Decision 1 forbids changing.

Decision 1 maps warehouse decimals to ``decimal.Decimal`` on all three backends and states,
as a prohibition, that the policy is **annotation-only**: it corrects what codegen writes into
a generated model, and introduces no runtime coercion.

The whole value path is one line. ``SemolinaCursor`` builds rows with ``batch.to_pylist()``;
pyarrow converts ``decimal128`` to ``decimal.Decimal`` there and Semolina passes the object
straight through. A money column therefore already yields a ``Decimal`` today, which is why
the annotation is the thing that was wrong. Adding a ``Decimal(``, ``float(``, or ``int(``
conversion anywhere on that path would invert the decision — it would make the value match the
annotation instead of the annotation match the value, and every measured row in
``47-TYPE-FIDELITY.md`` would then be describing Semolina's own conversion rather than the
warehouse's behaviour.

**Narrowed in Phase 49, from a file fence to a content fence (PD-06).** For Phase 48 this
module fenced ``cursor.py``, ``acursor.py`` and ``results.py`` by *path*: any diff naming one
of them failed. Phase 49 adds ``into``, ``iter_into``, ``fetch_df`` and ``fetch_polars`` to
both cursors — result-shaping methods that read a schema and delegate conversion to arrowmodel
or to ADBC — so under the old rule the gate turned red at Phase 49's first commit and would
have stayed red for the whole phase. Re-pointing :data:`DEFAULT_BASE_REF` at Phase 49's start
commit would not have helped, because the phase's own commits touch those files.

Saying it out loud, which is what the original docstring asked a later phase to do: Phase 49
adds methods to the value-path modules and adds **no value conversion**. The fence therefore
now names the thing Decision 1 actually prohibits — a numeric or decimal conversion introduced
into the row-construction code — rather than the filenames that happen to contain it.
``results.py`` stays fenced by path, because Phase 49 has no reason to touch it at all.

This is a genuine weakening and is recorded as such: a path fence catches edits a content
fence cannot imagine, and the prohibition it enforces was approved at a blocking human
checkpoint in Phase 47. The narrowing is documented in ``49-01-PLAN.md`` (PD-06) and restated
in ``49-01-SUMMARY.md`` so it is visible at phase verification rather than discovered later.

Enforced here rather than by review, because a fence nobody can run is a fence nobody checks.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
"""The repository root, two levels above ``tests/unit/``."""

FENCED_PATH_PATTERN = re.compile(r"^src/semolina/results\.py$")
"""
The one value-path module still fenced by path.

Was ``(cursor|acursor|results)`` for Phase 48. Narrowed to ``results.py`` alone in Phase 49
(PD-06): the two cursor modules legitimately gain result-shaping methods in that phase, while
``results.py`` — which defines ``Row`` itself — has no reason to change and keeps the stronger
guarantee.
"""

VALUE_PATH_MODULES = ("src/semolina/cursor.py", "src/semolina/acursor.py")
"""
The two modules whose row-construction code is fenced by content rather than by path.

Both may gain methods freely. What neither may gain is a value conversion inside the functions
named in :data:`ROW_CONSTRUCTION_FUNCTIONS`.
"""

ROW_CONSTRUCTION_FUNCTIONS = frozenset(
    {
        "__next__",
        "__anext__",
        "fetchall_rows",
        "fetchone_row",
        "fetchmany_rows",
    }
)
"""
The functions that turn driver output into ``Row`` objects — the value path itself.

Everything Decision 1 protects happens inside one of these five. A method that fetches an
Arrow table, a dataframe or a DTO is not here, because it hands the conversion to pyarrow,
pandas, polars or arrowmodel and expresses no opinion about the value.
"""

EXPECTED_FENCED_FUNCTIONS: dict[str, frozenset[str]] = {
    "src/semolina/cursor.py": frozenset(
        {"__next__", "fetchall_rows", "fetchone_row", "fetchmany_rows"}
    ),
    "src/semolina/acursor.py": frozenset(
        {"__anext__", "fetchall_rows", "fetchone_row", "fetchmany_rows"}
    ),
}
"""
Exactly which row-construction functions each module must contribute, by name.

Compared for equality rather than non-emptiness. "At least one was found" left three of a
module's four free to be renamed while the fence stayed green and guarded a quarter of what it
had — the failure mode the fence's own docstring claimed to catch, but only caught when
*every* name was renamed at once. Adding a row-construction function means adding it here, in
the same commit.
"""

FORBIDDEN_CONVERSION_NAMES = frozenset(
    {
        "float",
        "int",
        "complex",
        "Decimal",
        "round",
        "quantize",
        "to_integral_value",
        "to_integral_exact",
        "from_float",
        "normalize",
    }
)
"""
Call targets that would convert, round or requantize a value on the row path.

Matched on the bare callable name, so both ``Decimal(x)`` and ``decimal.Decimal(x)`` are
caught, as are ``value.quantize(...)`` and ``round(value, 2)``. Deliberately one obvious list
to extend rather than a clever expression: the next person adding a conversion idiom should be
able to see where to name it.
"""

BASE_REF_ENV_VAR = "SEMOLINA_SCOPE_FENCE_BASE"
"""Environment variable naming the ref to diff against. Overrides :data:`DEFAULT_BASE_REF`."""

DEFAULT_BASE_REF = "9f3c8b9"
"""
The commit Phase 48 started from (``docs(48): add pattern map``).

Deliberately **not** ``origin/main``. The prohibition is on what later phases change, and the
v0.7 milestone branch legitimately created ``src/semolina/acursor.py`` back in Phase 46, so
diffing against ``main`` reports that file and turns this gate permanently red for a reason
that has nothing to do with the Decimal policy. A gate that is always red is a gate someone
eventually deletes.

Left pointing at Phase 48's start commit through Phase 49 rather than moved forward. Under the
old path fence, re-pointing this constant was the escape hatch a later phase was expected to
use; Phase 49 took the other route the docstring allows — recording the decision and narrowing
what is fenced — so the ref still means what it says. It applies to
:func:`test_value_path_files_are_untouched`, which now guards ``results.py`` alone;
:func:`test_row_construction_introduces_no_value_conversion` reads the working tree and needs
no ref at all, which is why it cannot be skipped.
"""


def _resolve_base_ref() -> str:
    """
    Return the ref this branch is compared against.

    Returns:
        The value of :data:`BASE_REF_ENV_VAR` when set and non-empty, else
        :data:`DEFAULT_BASE_REF`.
    """
    return os.environ.get(BASE_REF_ENV_VAR) or DEFAULT_BASE_REF


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """
    Run a git subcommand and capture its output.

    Args:
        args: Arguments to pass to ``git``.

    Returns:
        The completed process, never raising on a non-zero exit — callers decide what a
        failure means.
    """
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _called_names(node: ast.AST) -> set[str]:
    """
    Collect the bare name of every callable invoked anywhere inside a node.

    Both call shapes are reduced to the same key: ``ast.Name`` contributes its ``id`` so
    ``Decimal(x)`` reads as ``Decimal``, and ``ast.Attribute`` contributes its ``attr`` so
    ``decimal.Decimal(x)`` and ``value.quantize(...)`` do too. Losing the qualifier is the
    point — an import alias must not be able to smuggle a conversion past the fence.

    Args:
        node: Any AST node; every ``ast.Call`` beneath it is visited.

    Returns:
        The set of called names.
    """
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _functions_by_name(tree: ast.AST) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    """
    Index every function defined anywhere in a module by its bare name.

    A list per name rather than a single node, because a module may define the same method
    name on two classes and the fence has no reason to prefer either.

    Args:
        tree: The parsed module.

    Returns:
        Name -> the definitions carrying it.
    """
    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.setdefault(node.name, []).append(node)
    return functions


def scan_source(source: str) -> tuple[set[str], list[str]]:
    """
    Run the content fence over one module's source.

    Factored out of the fence test so the fence can be pointed at a source string that does
    not exist on disk. Without that, "the fence catches a delegated conversion" is a claim
    nothing can check, and the fence's coverage is measured only by whether the real modules
    happen to be clean today — which they are, and which says nothing.

    Delegation is followed one hop: a conversion moved out of ``__next__`` into a helper the
    module defines and ``__next__`` calls is still a conversion on the row path. One hop and
    not the full call graph, because the second hop reaches ``fetchall`` and from there most
    of the module, and a fence that walks everything stops being a statement about the row
    path.

    Args:
        source: The module's text.

    Returns:
        The names of the fenced functions found, and one finding per conversion reached.
    """
    tree = ast.parse(source)
    functions = _functions_by_name(tree)
    fenced = [
        node
        for name, nodes in functions.items()
        if name in ROW_CONSTRUCTION_FUNCTIONS
        for node in nodes
    ]

    findings: list[str] = []
    for function in fenced:
        called = _called_names(function)
        for name in sorted(called & FORBIDDEN_CONVERSION_NAMES):
            findings.append(f"{function.name} (line {function.lineno}) calls {name}")

    return {function.name for function in fenced}, findings


def test_value_path_files_are_untouched() -> None:
    """
    No commit on this branch modifies results.py.

    Skips with an explicit message when the base ref cannot be resolved. A gate that
    passes when it could not run is worse than no gate: it reports the same green as a
    gate that ran and found nothing, so the one condition it exists to catch would be
    indistinguishable from success.
    """
    base_ref = _resolve_base_ref()

    resolved = _git("rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}")
    if resolved.returncode != 0:
        pytest.skip(
            f"Scope fence did NOT run: base ref {base_ref!r} is not resolvable in this "
            f"repository (a shallow clone will not carry it). Set {BASE_REF_ENV_VAR} to a "
            "ref that exists, or deepen the clone, to enforce the fence."
        )

    merge_base = _git("merge-base", base_ref, "HEAD")
    if merge_base.returncode != 0:
        pytest.skip(
            f"Scope fence did NOT run: no merge base between {base_ref!r} and HEAD "
            f"({merge_base.stderr.strip()})."
        )

    diff = _git("diff", "--name-only", f"{merge_base.stdout.strip()}..HEAD")
    assert diff.returncode == 0, f"git diff failed: {diff.stderr.strip()}"

    touched = [path for path in diff.stdout.splitlines() if FENCED_PATH_PATTERN.match(path.strip())]

    assert not touched, (
        f"This branch modifies the fenced value-path modules {touched}. "
        "47-DECISIONS.md Decision 1 is annotation-only: the annotation is corrected to "
        "the value, never the reverse. If a value genuinely needs converting, that is a "
        "new decision, not an implementation detail."
    )


def test_row_construction_introduces_no_value_conversion() -> None:
    """
    No row-construction function on either cursor converts, rounds or requantizes a value.

    Reads the working tree rather than a diff, so it needs no base ref and can never skip.
    That is the half of the fence that survives Phase 49's narrowing, and it is stronger than
    the path rule in one respect: it also fails on a conversion that has been sitting there
    since before the base commit.
    """
    findings: list[str] = []

    for relative in VALUE_PATH_MODULES:
        path = REPO_ROOT / relative
        assert path.is_file(), (
            f"Scope fence cannot run: {relative} does not exist. If the module moved, "
            "re-point VALUE_PATH_MODULES in the same commit."
        )

        fenced_names, module_findings = scan_source(path.read_text(encoding="utf-8"))

        assert fenced_names, (
            f"Scope fence found none of {sorted(ROW_CONSTRUCTION_FUNCTIONS)} in {relative}. "
            "A rename emptied the fence, which would leave it passing while guarding "
            "nothing — update ROW_CONSTRUCTION_FUNCTIONS in the same commit as the rename."
        )

        findings.extend(f"{relative}::{finding}" for finding in module_findings)

    assert not findings, (
        f"Value conversion introduced on the row-construction path: {findings}. "
        "47-DECISIONS.md Decision 1 is annotation-only: the annotation is corrected to "
        "the value, never the reverse. If a value genuinely needs converting, that is a "
        "new decision, not an implementation detail."
    )


class TestFenceCatchesRealisticBypasses:
    """
    What the fence would catch, asserted against sources written to slip past it.

    The fence over the real modules is green, and a green fence proves nothing on its own:
    it reads the same as a fence that cannot see anything. Each case below is a way a value
    conversion could plausibly arrive on the row path, run through the fence's own
    :func:`scan_source`. All three were measured passing before the fence was tightened.
    """

    def test_a_conversion_delegated_to_a_helper_is_caught(self) -> None:
        """
        Moving ``float(v)`` one call out of ``__next__`` used to empty the fence completely.

        The most likely accidental bypass, because extracting a helper is the ordinary thing
        to do to a growing method and nobody doing it would think they were touching a fence.
        """
        source = (
            "class C:\n"
            "    def _coerce(self, v):\n"
            "        return float(v)\n"
            "\n"
            "    def __next__(self):\n"
            "        return self._coerce(self._value)\n"
        )

        _fenced, findings = scan_source(source)

        assert findings, "A conversion one hop from __next__ went unreported"

    def test_an_arrow_level_cast_is_caught(self) -> None:
        """
        The fenced functions hold Arrow batches, so a cast is where a conversion would land.

        Not a hypothetical shape: it is the one-line way to make every decimal column arrive
        as a float, and it never mentions ``float`` or ``Decimal`` at all.
        """
        source = (
            "class C:\n"
            "    def __next__(self):\n"
            "        batch = self._batch.cast(self._float_schema)\n"
            "        return Row(batch)\n"
        )

        _fenced, findings = scan_source(source)

        assert findings, "An Arrow-level cast on the row path went unreported"

    def test_a_pandas_astype_is_caught(self) -> None:
        """``float`` appears here as an argument, never as a call, so name matching missed it."""
        source = (
            "class C:\n"
            "    def fetchall_rows(self):\n"
            "        return self._cursor.fetch_df().astype(float)\n"
        )

        _fenced, findings = scan_source(source)

        assert findings, "A dataframe-level astype on the row path went unreported"

    def test_a_renamed_function_no_longer_leaves_the_fence_quietly_green(self) -> None:
        """
        Three of four renamed used to leave the fence passing while guarding a quarter.

        The old rule asked only that *some* fenced name be found per module. This asserts the
        weaker premise the exact-set comparison rests on: a module missing one of its expected
        names is distinguishable from one carrying all of them.
        """
        source = "class C:\n    def __next__(self):\n        return Row(self._batch.to_pylist())\n"

        fenced, _findings = scan_source(source)

        assert fenced != EXPECTED_FENCED_FUNCTIONS["src/semolina/cursor.py"]

    def test_the_real_row_path_idioms_are_not_flagged(self) -> None:
        """
        The negative control: ``to_pylist`` and ``zip``/``dict`` row building stay green.

        A fence that fired on the row path as it is actually written would be deleted within
        a week, so the tightenings have to be shown to discriminate rather than merely to
        fire.
        """
        source = (
            "class C:\n"
            "    def _column_names(self):\n"
            "        return [d[0] for d in self._cursor.description]\n"
            "\n"
            "    def fetchall_rows(self):\n"
            "        names = self._column_names()\n"
            "        return [Row(dict(zip(names, r, strict=True))) "
            "for r in self._cursor.fetchall()]\n"
            "\n"
            "    def __next__(self):\n"
            "        return Row(self._batch.to_pylist()[0])\n"
        )

        _fenced, findings = scan_source(source)

        assert findings == []
