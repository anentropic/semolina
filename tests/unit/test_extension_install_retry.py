"""
The test fixtures' ``INSTALL semantic_views`` retries once (TEST-04).

Each xdist worker installs the community extension when it builds its fixtures, and a
download from the community repository can fail transiently on a shared runner. One retry
absorbs that; a second failure is real and must surface.
"""

from __future__ import annotations

import pytest
from duckdb_extension import load_semantic_views

duckdb = pytest.importorskip("duckdb")


class _FlakyConnection:
    """Fails ``INSTALL`` a set number of times, then succeeds; records every statement."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.statements: list[str] = []

    def execute(self, sql: str) -> None:
        self.statements.append(sql)
        if sql.startswith("INSTALL") and self.failures:
            self.failures -= 1
            raise duckdb.IOException("Failed to download extension")


def test_one_failed_install_is_retried() -> None:
    """A transient failure is retried, then the extension is loaded."""
    conn = _FlakyConnection(failures=1)
    load_semantic_views(conn)
    assert conn.statements == [
        "INSTALL semantic_views FROM community",
        "INSTALL semantic_views FROM community",
        "LOAD semantic_views",
    ]


def test_a_second_failure_is_raised() -> None:
    """Two failures in a row are not a flake: the error reaches the test."""
    conn = _FlakyConnection(failures=2)
    with pytest.raises(duckdb.IOException):
        load_semantic_views(conn)
    assert "LOAD semantic_views" not in conn.statements


def test_a_working_install_runs_once() -> None:
    """With nothing failing, the extension is installed once and loaded."""
    conn = _FlakyConnection(failures=0)
    load_semantic_views(conn)
    assert conn.statements == ["INSTALL semantic_views FROM community", "LOAD semantic_views"]
