"""
A runnable gate on the three modules Phase 48 is forbidden to touch.

``47-DECISIONS.md`` Decision 1 maps warehouse decimals to ``decimal.Decimal`` on all three
backends and states, as a prohibition, that the policy is **annotation-only**: it corrects
what codegen writes into a generated model, and introduces no runtime coercion.

The whole value path is one line. ``SemolinaCursor`` builds rows with
``batch.to_pylist()`` (``src/semolina/cursor.py:281``); pyarrow converts ``decimal128`` to
``decimal.Decimal`` there and Semolina passes the object straight through. A money column
therefore already yields a ``Decimal`` today, which is why the annotation is the thing that
was wrong. Adding a ``Decimal(``, ``float(``, or ``int(`` conversion anywhere on that path
would invert the decision — it would make the value match the annotation instead of the
annotation match the value, and every measured row in ``47-TYPE-FIDELITY.md`` would then be
describing Semolina's own conversion rather than the warehouse's behaviour.

Enforced here rather than by review, because a fence nobody can run is a fence nobody
checks. The test compares the working branch against a base ref and fails on any diff that
names one of the three modules.
"""

from __future__ import annotations

import os
import re
import subprocess

import pytest

FENCED_PATH_PATTERN = re.compile(r"^src/semolina/(cursor|acursor|results)\.py$")
"""The three modules on the value path. No Phase 48 plan may appear in a diff against them."""

BASE_REF_ENV_VAR = "SEMOLINA_SCOPE_FENCE_BASE"
"""Environment variable naming the ref to diff against. Overrides :data:`DEFAULT_BASE_REF`."""

DEFAULT_BASE_REF = "9f3c8b9"
"""
The commit Phase 48 started from (``docs(48): add pattern map``).

Deliberately **not** ``origin/main``. The prohibition is on what Phase 48 changes, and the
v0.7 milestone branch legitimately created ``src/semolina/acursor.py`` back in Phase 46, so
diffing against ``main`` reports that file and turns this gate permanently red for a reason
that has nothing to do with the Decimal policy. A gate that is always red is a gate someone
eventually deletes.

Pinning a commit means the fence keeps applying to work done after Phase 48 as well. That is
the intended reading rather than an accident: 47-DECISIONS.md says introducing value coercion
requires a new decision, so a later phase that needs to touch these modules should have to
say so out loud — by re-pointing this constant in the same commit that records the decision,
or by setting :data:`BASE_REF_ENV_VAR` for a deliberate one-off run.
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


def test_value_path_files_are_untouched() -> None:
    """
    No commit on this branch modifies cursor.py, acursor.py, or results.py.

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
