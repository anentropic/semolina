"""Tests for CLI utility functions."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
import typer
from rich.console import Console

if TYPE_CHECKING:
    from pathlib import Path

from cubano.cli.utils import resolve_input_paths


def make_test_stderr() -> Console:
    """Create a Console writing to a StringIO buffer for test isolation."""
    return Console(file=io.StringIO(), stderr=True)


class TestResolveInputPaths:
    def test_explicit_py_file(self, tmp_path: Path) -> None:
        f = tmp_path / "models.py"
        f.write_text("")
        result = resolve_input_paths(str(f), make_test_stderr())
        assert result == [f.resolve()]

    def test_nonexistent_file_raises_exit(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit):
            resolve_input_paths(str(tmp_path / "nonexistent.py"), make_test_stderr())

    def test_directory_scans_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "other.txt").write_text("")
        result = resolve_input_paths(str(tmp_path), make_test_stderr())
        names = {p.name for p in result}
        assert "a.py" in names
        assert "b.py" in names
        assert "other.txt" not in names

    def test_directory_excludes_pycache(self, tmp_path: Path) -> None:
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("")
        (tmp_path / "real.py").write_text("")
        result = resolve_input_paths(str(tmp_path), make_test_stderr())
        assert all("__pycache__" not in str(p) for p in result)
