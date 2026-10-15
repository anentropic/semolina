"""
Engine classes for ``--backend dotted.path.ClassName`` tests that must fail to construct.

``--backend`` instantiates the named class with no arguments, so a class whose constructor
needs one, or raises, is the realistic way a user's own engine fails before codegen has
done anything.
"""

from __future__ import annotations


class NeedsArguments:
    """An engine whose constructor takes a required argument."""

    def __init__(self, pool: object) -> None:
        """
        Keep the pool a real engine would be handed.

        Args:
            pool: Anything; ``--backend`` never passes one.
        """
        self.pool = pool


class RaisesInInit:
    """An engine whose constructor raises, as one reading its own config might."""

    def __init__(self) -> None:
        """
        Fail the way a misconfigured custom engine does.

        Raises:
            RuntimeError: Always.
        """
        msg = "CUSTOM_ENGINE_DSN is not set"
        raise RuntimeError(msg)
