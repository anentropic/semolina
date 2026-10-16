"""
Copied cassettes are marked as copied (TEST-02).

Only ``test_queries`` and ``test_introspect`` record against a warehouse. Every other
cassette was copied byte for byte from one of their recordings, so a reader seeing it pass
learns only that the SQL still matches a recording, not that anything was run live. Such a
test and its cassette carry ``copied`` in their name, so the test id says so wherever it is
reported. The marking is checked here because a new copied cassette would otherwise look
exactly like a recorded one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CASSETTES = Path(__file__).resolve().parents[1] / "integration" / "cassettes"

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
