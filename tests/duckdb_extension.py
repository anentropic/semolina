"""
Install and load the ``semantic_views`` community extension for test fixtures.

Fixtures that build a DuckDB database directly go through :func:`load_semantic_views`, so
the one retry below covers them. Engine-based fixtures install through the library's pool
connect listener instead, which has no retry.

``duckdb`` is imported inside the function: it is an optional extra, and the root conftest
imports this module, so a module-level import would stop the suite loading without it.
"""

from __future__ import annotations

from typing import Protocol

INSTALL = "INSTALL semantic_views FROM community"
LOAD = "LOAD semantic_views"


class _Executes(Protocol):
    def execute(self, sql: str, /) -> object: ...


def load_semantic_views(conn: _Executes) -> None:
    """
    Install the extension, retrying once, then load it.

    Each xdist worker installs into the shared user-level extension directory, and the
    download from the community repository can fail transiently on a shared runner (CI
    warms the cache first, but a local ``-n auto`` run does not). One retry absorbs a
    transient failure; a second failure is raised, because it is not one.

    Args:
        conn: A DuckDB connection, or anything with its ``execute``.

    Raises:
        duckdb.Error: When the install fails twice.
    """
    import duckdb

    try:
        conn.execute(INSTALL)
    except duckdb.Error:
        conn.execute(INSTALL)
    conn.execute(LOAD)
