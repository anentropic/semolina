"""
CLI utility functions for Semolina codegen commands.

Provides path resolution, stderr console creation, and progress helpers.
"""

from __future__ import annotations

import glob as _glob
import sys
from pathlib import Path

import typer
from rich.console import Console


def make_stderr_console(verbose: bool = False) -> Console:
    """
    Create a Rich Console writing to stderr for diagnostic output.

    Args:
        verbose: If True, suppress no output (show everything). If False, only
            show warnings and errors.

    Returns:
        Configured Rich Console for stderr.
    """
    return Console(file=sys.stderr, stderr=True)


def resolve_input_paths(input_spec: str, stderr: Console) -> list[Path]:
    """
    Resolve an input specification to a list of Python file paths.

    Handles three forms:
    - Explicit file path: must exist, returned as single-element list
    - Directory path: scanned recursively for *.py files
    - Glob pattern: expanded via pathlib from cwd

    Fails immediately (raises SystemExit via typer.Exit) if an explicit
    file path doesn't exist or can't be read.

    Args:
        input_spec: File path, directory path, or glob pattern string.
        stderr: Rich Console for diagnostic messages.

    Returns:
        Sorted list of resolved .py file paths.

    Raises:
        typer.Exit: If an explicit path doesn't exist or is unreadable.
    """
    path = Path(input_spec)

    # If input contains glob special characters, treat as glob regardless of suffix.
    # This handles patterns like '/path/to/*.py' which have suffix '.py' but aren't
    # explicit file paths.
    _GLOB_CHARS = {"*", "?", "["}
    is_glob = any(ch in input_spec for ch in _GLOB_CHARS)

    if not is_glob:
        # Explicit file: must exist
        if path.suffix == ".py":
            if not path.exists():
                stderr.print(
                    f"[bold red]Error:[/bold red] File not found: [cyan]{path}[/cyan]\n"
                    f"  Check the path and try again."
                )
                raise typer.Exit(code=1)
            if not path.is_file():
                stderr.print(f"[bold red]Error:[/bold red] Not a file: [cyan]{path}[/cyan]")
                raise typer.Exit(code=1)
            return [path.resolve()]

        # Directory: scan recursively for *.py files
        if path.is_dir():
            files = sorted(path.rglob("*.py"))
            # Exclude __pycache__ and hidden directories
            files = [
                f
                for f in files
                if "__pycache__" not in f.parts and not any(p.startswith(".") for p in f.parts)
            ]
            return files

        # Explicit directory path that doesn't exist: fail immediately
        if not path.suffix and not path.exists():
            stderr.print(
                f"[bold red]Error:[/bold red] Directory not found: [cyan]{path}[/cyan]\n"
                f"  Check the path and try again."
            )
            raise typer.Exit(code=1)

    # Glob pattern: expand via glob.glob which handles both relative and absolute patterns.
    # Path.cwd().glob() raises NotImplementedError for absolute patterns in Python 3.14+.
    matched = sorted(Path(m) for m in _glob.glob(input_spec, recursive=True))
    py_files = [f for f in matched if f.suffix == ".py" and f.is_file()]
    return py_files
