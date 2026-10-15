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


FIXTURE_SECRET = "s3cr3t-pw"
"""
The password :class:`RaisesValidationError` builds its settings from.

Short on purpose, and so is the dict it sits in: pydantic elides the middle of a long
``input_value`` repr, and a secret cut in half by that elision would make a leak look redacted.
"""


class RaisesValidationError:
    """An engine whose constructor validates its own settings with pydantic, and fails."""

    def __init__(self) -> None:
        """
        Validate a settings dict that carries a password and lacks a required field.

        Raises:
            pydantic.ValidationError: Always; its ``str()`` quotes the whole input dict.
        """
        import pydantic

        class _Settings(pydantic.BaseModel):
            account: str
            user: str
            password: str

        _Settings.model_validate({"user": "u", "password": FIXTURE_SECRET})


class ValidatesOnIntrospect:
    """An engine that builds fine and validates its settings only when it is first used."""

    def introspect(self, view_name: str) -> object:
        """
        Fail the way an engine that connects lazily, and validates while doing it, fails.

        Args:
            view_name: Ignored.

        Raises:
            pydantic.ValidationError: Always; its ``str()`` quotes the whole input dict.
        """
        RaisesValidationError()
        raise AssertionError(view_name)  # pragma: no cover
