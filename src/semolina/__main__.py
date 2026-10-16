"""
Entry point for the ``semolina`` command and for ``python -m semolina``.

The command's packages (typer, rich, jinja2 and griffe) are the ``[cli]`` extra, not base
dependencies, but the console script is installed either way. So this module imports none of
them: it checks they are present first, and without them prints how to install the extra
instead of failing on an import with a traceback.
"""

from __future__ import annotations

import importlib.util
import sys

__all__ = ["main"]

CLI_MODULES = ("typer", "rich", "jinja2", "griffe")
"""The modules the ``[cli]`` extra installs, by import name."""

INSTALL_HINT = 'Install the command with: pip install "semolina[cli]"'
"""The fix for a missing or broken ``[cli]`` extra."""

EXIT_MISSING_EXTRA = 2
"""The code the CLI uses for a missing optional package, so this matches its own table."""


def _listed(names: list[str]) -> str:
    """
    Join names as prose: ``a``, ``a and b``, ``a, b and c``.

    Args:
        names: At least one name.

    Returns:
        The names joined for a sentence.
    """
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def main() -> None:
    """
    Run the Semolina CLI, or explain how to install it.

    Raises:
        SystemExit: With code 2 when a package from the ``[cli]`` extra is missing or fails
            to import.
    """
    missing = [name for name in CLI_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        sys.stderr.write(
            f"The semolina command needs {_listed(missing)}, which "
            f"{'is' if len(missing) == 1 else 'are'} not installed. {INSTALL_HINT}\n"
        )
        raise SystemExit(EXIT_MISSING_EXTRA)

    # find_spec shows a package can be found, not that it imports: a partial install (a
    # dependency removed, a stale version) still fails here, and gets the same hint.
    try:
        from semolina.cli import app
    except ImportError as error:
        sys.stderr.write(f"The semolina command could not load ({error}). {INSTALL_HINT}\n")
        raise SystemExit(EXIT_MISSING_EXTRA) from None

    app()


if __name__ == "__main__":
    main()
