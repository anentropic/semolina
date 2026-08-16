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

**Tightened after code review (WR-04).** The narrowed fence turned out to be weaker than that
record accounted for. Three realistic bypasses came back green against it: a conversion moved
one call out of ``__next__`` into a helper, an Arrow ``batch.cast(...)``, and a dataframe
``.astype(float)``. It also asked only that *some* fenced name be found per module, so
renaming three of a module's four left it passing while guarding a quarter. All three holes
are closed, and :class:`TestFenceCatchesRealisticBypasses` aims the fence at each bypass
rather than leaving "this fence can see things" as an untested claim — the real modules are
clean, so the fence over them reads identically whether it works or not.

Enforced here rather than by review, because a fence nobody can run is a fence nobody checks.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest
from _pytest.outcomes import Failed, Skipped

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
        # Arrow- and dataframe-level conversions. The row path is Arrow-shaped, so a
        # conversion introduced here would most naturally be spelled as a cast on the batch
        # or on a dataframe built from it, never as a Python-level `float(v)` per value.
        "cast",
        "astype",
        "to_pandas",
        "to_numpy",
        "float64",
        "float32",
    }
)
"""
Call targets that would convert, round or requantize a value on the row path.

Matched on the bare callable name, so both ``Decimal(x)`` and ``decimal.Decimal(x)`` are
caught, as are ``value.quantize(...)`` and ``round(value, 2)``. Deliberately one obvious list
to extend rather than a clever expression: the next person adding a conversion idiom should be
able to see where to name it.

``cast`` is on the list for ``batch.cast(schema)`` and collides with :func:`typing.cast`, which
is not a value conversion. That collision is accepted rather than worked around: no fenced or
delegated function uses ``typing.cast`` today, and hoisting one out of a row-construction
function is cheaper than teaching this list to tell two same-named callables apart. ``to_pylist``
is deliberately absent — it *is* the row path, not a conversion applied to it.
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
        for delegate_name in sorted(called):
            if delegate_name in ROW_CONSTRUCTION_FUNCTIONS:
                # Fenced on its own account, so its own conversions are already reported and
                # reporting them again under every caller would be noise.
                continue
            for delegate in functions.get(delegate_name, []):
                for name in sorted(_called_names(delegate) & FORBIDDEN_CONVERSION_NAMES):
                    findings.append(
                        f"{function.name} (line {function.lineno}) delegates to "
                        f"{delegate_name} (line {delegate.lineno}), which calls {name}"
                    )

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

        assert fenced_names == EXPECTED_FENCED_FUNCTIONS[relative], (
            f"Scope fence found {sorted(fenced_names)} in {relative}, expected "
            f"{sorted(EXPECTED_FENCED_FUNCTIONS[relative])}. A rename or a new "
            "row-construction function silently changes what is guarded — update "
            "ROW_CONSTRUCTION_FUNCTIONS and EXPECTED_FENCED_FUNCTIONS in the same commit."
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


class TestTheFenceCannotSkipItselfInCI:
    """
    WR-05: the path half of the fence never ran in this project's CI.

    ``test_value_path_files_are_untouched`` skips when its base ref will not resolve, and
    ``ci.yml``'s test job checked out at the default shallow depth of 1 while
    :data:`DEFAULT_BASE_REF` sits 170-odd commits back. So after PD-06 narrowed the path fence
    down to ``results.py`` alone, the one thing it still guarded was guarded only on a
    developer's full local clone.

    The skip is right locally, where a shallow clone is a foreign condition the contributor
    did not choose. It is wrong in CI, where an unresolvable ref means the gate was configured
    away — and a skip reports that as the same green a gate that ran and found nothing does.
    """

    UNRESOLVABLE_REF = "0000000000000000000000000000000000000000"
    """A well-formed SHA that will not resolve, standing in for a shallow clone's history."""

    @staticmethod
    def fence_outcome() -> str:
        """
        Run the path fence and name what it did, rather than letting the outcome propagate.

        A ``Skipped`` allowed out of a test body skips *that* test, so asserting the fence
        fails cannot be written as ``pytest.raises(Failed)``: the wrong behaviour would report
        as a skip, which is the very thing being complained about.

        Returns:
            ``"failed"``, ``"skipped"`` or ``"passed"``.
        """
        try:
            test_value_path_files_are_untouched()
        except Failed:
            return "failed"
        except Skipped:
            return "skipped"
        return "passed"

    def test_it_fails_rather_than_skipping_when_ci_is_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In CI an unresolvable base ref is a misconfiguration, not an environment quirk."""
        monkeypatch.setenv("CI", "true")
        monkeypatch.setenv(BASE_REF_ENV_VAR, TestTheFenceCannotSkipItselfInCI.UNRESOLVABLE_REF)

        assert TestTheFenceCannotSkipItselfInCI.fence_outcome() == "failed"

    def test_it_still_skips_outside_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A contributor on a shallow clone gets a message, not a red suite."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv(BASE_REF_ENV_VAR, TestTheFenceCannotSkipItselfInCI.UNRESOLVABLE_REF)

        assert TestTheFenceCannotSkipItselfInCI.fence_outcome() == "skipped"

    def test_the_default_base_ref_resolves_here(self) -> None:
        """
        The premise: CI can only enforce a ref that exists once the clone is deep enough.

        Fails on a shallow clone, which is the point — this is the assertion that would have
        caught the ``fetch-depth`` gap directly, rather than through the fence quietly
        skipping.
        """
        resolved = _git("rev-parse", "--verify", "--quiet", f"{DEFAULT_BASE_REF}^{{commit}}")

        assert resolved.returncode == 0, (
            f"{DEFAULT_BASE_REF!r} does not resolve. In CI this means the checkout is "
            "shallow: set fetch-depth: 0 on the job that runs pytest."
        )
