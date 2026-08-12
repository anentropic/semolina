"""
Python code renderer for reverse codegen.

Converts IntrospectedView objects into formatted, importable Python source code
suitable for use as Semolina SemanticView model classes.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from semolina.codegen.introspector import IntrospectedView

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_ROLE_TO_CLASS = {"metric": "Metric", "dimension": "Dimension", "fact": "Fact"}

# Annotation prefix -> the stdlib import line that makes the annotation resolvable.
# Matched by substring containment against the *resolved* annotation, never by equality:
# a metric annotation carries a ``| None`` suffix (Decision 2), so an exact-membership
# test would stop matching for exactly the fields that need the import, and the generated
# module would raise NameError for datetime-typed metrics alone.
_STDLIB_MODULE_PREFIXES: dict[str, str] = {
    "datetime.": "import datetime",
    "decimal.": "import decimal",
}

# Names every generated module imports from semolina. Rendered as a single
# ``from semolina import ...`` statement built from a set: ruff's isort does not merge two
# separate ``from semolina import`` statements, so emitting a second one would ship
# duplicated-looking output whenever the optional ``codegen-lint`` extra is absent.
_SEMOLINA_IMPORT_NAMES = frozenset({"SemanticView", "Metric", "Dimension", "Fact"})

# Names imported from semolina only when an annotation uses them. Unlike the four above,
# these are types rather than field descriptors, so a module that needs none of them should
# not import any: an unused import is noise in a file the user reads and edits.
_CONDITIONAL_SEMOLINA_IMPORT_NAMES = frozenset({"JsonValue"})

# A field earns a raw-warehouse-type comment when its Python annotation does not name the
# warehouse type it came from. Both lists are explicit rather than heuristic so the rule is
# reviewable: adding a map key is a decision about a type, and whether that key loses
# information is a second decision, made here.
#
# Matched against IntrospectedField.data_type, before metric nullability is appended.
_RAW_TYPE_COMMENT_ANNOTATIONS = frozenset({"decimal.Decimal", "JsonValue"})

# Matched against the raw type's base name, normalised the way the type map normalises its
# own lookups. These are the D-03 cases where the annotation is a faithful description of
# the *value* and still says nothing about the column: a DuckDB UUID arrives as a str, a
# JSON column as unparsed str text, an ENUM as a str from a dictionary-encoded column.
_RAW_TYPE_COMMENT_BASE_TYPES = frozenset(
    {
        "UUID",
        "JSON",
        "ENUM",
        "TIMESTAMP_S",
        "TIMESTAMP_MS",
        "TIMESTAMP_NS",
        "INTERVAL",
    }
)


def _python_str_literal(value: str) -> str:
    """
    Render a value as a Python string literal, escaped by Python's own escaper.

    Every string the template writes into generated source comes from warehouse metadata,
    and the documented workflow (``docs/src/how-to/codegen.rst``) redirects that source to a
    file the user then *imports*. A value that closes its own literal is therefore
    module-level code execution, not a formatting bug. ``repr`` is the honest primitive
    here: it owns quoting, backslashes and control characters together, so there is no
    hand-rolled escape table to get subtly wrong.

    Jinja's ``autoescape`` is not an alternative -- it escapes for HTML, which would turn a
    ``&`` in a column name into ``&amp;`` while leaving a quote just as dangerous.

    The generated file's house style is double quotes, and ``repr`` prefers single ones, so
    the delimiters are swapped back when the body carries no double quote to escape. That
    keeps output byte-identical for every name that does not contain a quote, which is all
    of them in practice.

    Args:
        value: The raw string to embed.

    Returns:
        A Python string literal whose value is exactly ``value``.

    Example:
        .. code-block:: python

            from semolina.codegen.python_renderer import _python_str_literal

            _python_str_literal("order_id")
            # '"order_id"'
    """
    literal = repr(value)
    if literal.startswith("'") and '"' not in value:
        return f'"{literal[1:-1]}"'
    return literal


def _docstring_body(text: str) -> str:
    r"""
    Escape text for the inside of a triple-double-quoted Python string.

    ``repr`` is used for every other interpolated string, but not here: it would collapse a
    multi-line column comment onto one line with ``\n`` escapes, and a field docstring is
    something the user reads. Keeping the triple-quoted form means escaping only the two
    characters that can end it early -- a backslash, and a quote that could complete the
    closing delimiter.

    Every ``"`` is escaped rather than only the runs that would actually terminate the
    literal. A rule that has to reason about run lengths and trailing positions is a rule
    that gets an edge case wrong; ``""`` immediately before the closing delimiter is enough
    to break it, and so is a lone trailing ``"``.

    Args:
        text: The raw description.

    Returns:
        The body to place between the triple-quote delimiters.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


@dataclass
class _FieldContext:
    """
    Intermediate rendering context for a single field.

    Attributes:
        name: Python attribute name for the field.
        field_class: Semolina class name: 'Metric', 'Fact', or 'Dimension'.
        docstring_body: Field description, escaped for the inside of a
            triple-quoted literal by :func:`_docstring_body`. Empty string if none.
        type_comment: Text of the ``#`` comment emitted above the field, already
            collapsed to a single line. Either the ``TODO: <raw>`` text for an
            unmapped type or the bare warehouse type for an annotation that does
            not name it. Empty string when the field earns no comment.
        data_type: Python type string for the Generic subscript (e.g., 'int',
            'str', 'datetime.date', 'Any'). Never empty.
        source_literal: The original warehouse column name as a ready-quoted Python
            string literal, when it differs from the Pythonic field name. Emitted as
            ``source=<literal>`` in the generated field constructor. None when not
            needed. Pre-quoted rather than raw so the template never interpolates an
            unescaped warehouse string into source.
    """

    name: str
    field_class: str
    docstring_body: str
    type_comment: str
    data_type: str
    source_literal: str | None


@dataclass
class _ModelContext:
    """
    Intermediate rendering context for a single view.

    Attributes:
        class_name: PascalCase Python class name.
        view_literal: The warehouse view name as a ready-quoted Python string literal,
            for the same reason as ``_FieldContext.source_literal``.
        fields: Ordered list of field rendering contexts.
    """

    class_name: str
    view_literal: str
    fields: list[_FieldContext]


def _field_class_for(field_type: str) -> str:
    """
    Return the Semolina class name for a given field type string.

    Args:
        field_type: One of 'metric', 'fact', or 'dimension'.

    Returns:
        Semolina class name: 'Metric', 'Fact', or 'Dimension'.

    Raises:
        ValueError: If ``field_type`` is not one of the recognized lowercase
            roles. The generator fails loudly on schema drift rather than
            silently mislabeling a column as a Dimension.
    """
    try:
        return _ROLE_TO_CLASS[field_type]
    except KeyError:
        raise ValueError(f"Unrecognized field role: {field_type!r}") from None


def _annotation_hides_raw_type(annotation: str, raw_type: str) -> bool:
    """
    Report whether a Python annotation fails to name the warehouse type it came from.

    Two independent reasons a field earns a raw-type comment, checked in this order:
    the annotation is one that never names its source (``decimal.Decimal`` says nothing
    about precision or scale), or the warehouse type is one no faithful annotation can
    describe (a DuckDB ``UUID`` arrives as a plain ``str``).

    Args:
        annotation: ``IntrospectedField.data_type``, before metric nullability is applied.
        raw_type: ``IntrospectedField.raw_type``, the warehouse's own spelling.

    Returns:
        True when the generated model should carry the raw type as a comment.
    """
    if annotation in _RAW_TYPE_COMMENT_ANNOTATIONS:
        return True

    # Normalised the way the type map normalises its own lookups, so "ENUM('a','b')" and
    # "TIMESTAMP_MS" are compared on the same footing as the keys they were mapped by.
    base = raw_type.split("(")[0].strip().upper()
    return base in _RAW_TYPE_COMMENT_BASE_TYPES


def metric_annotation(annotation: str) -> str:
    """
    Apply metric nullability to a resolved annotation.

    Decision 2 (47-DECISIONS.md): metric annotations are uniformly ``T | None``. SUM, AVG,
    MIN and MAX all return NULL for a group whose inputs are all NULL; COUNT never does and
    is a documented over-approximation.

    This is the ONLY place nullability is applied, and it is shared rather than duplicated:
    ``semolina codegen --check`` must decorate a *probed* annotation by the same rule before
    comparing it against a committed one, or every metric would report spurious drift. Two
    copies of Decision 2's stance would drift apart the first time one of them was revisited.

    Putting the rule in a type map or an engine instead would push ``| None`` into
    ``IntrospectedField.data_type``, which the type-fidelity artifact and ``--check`` both
    read as the *mapped* annotation — nullability is a rendering concern, not a mapping one.

    Args:
        annotation: A resolved Python annotation string, e.g. ``'decimal.Decimal'``.

    Returns:
        The annotation with ``| None`` appended.

    Example:
        .. code-block:: python

            from semolina.codegen.python_renderer import metric_annotation

            metric_annotation("decimal.Decimal")
            # 'decimal.Decimal | None'
    """
    return f"{annotation} | None"


def _build_model_context(view: IntrospectedView) -> _ModelContext:
    """
    Convert an IntrospectedView into a _ModelContext ready for Jinja2 rendering.

    Args:
        view: Warehouse introspection result.

    Returns:
        Rendering context with resolved field classes, docstrings, type comments,
        data_type strings, and source_name values.
    """
    fields: list[_FieldContext] = []
    for f in view.fields:
        # Collapse any whitespace (including embedded newlines from pretty-printed
        # warehouse type descriptors) so the comment can never span multiple physical
        # lines and break the generated code.
        type_comment = ""
        if f.data_type is not None and f.data_type.startswith("TODO:"):
            type_comment = " ".join(f.data_type.split())
        # D-03: a mapped type loses the TODO channel, so the warehouse's own spelling is
        # preserved here for any annotation that does not name it.
        elif (
            f.data_type is not None
            and f.raw_type is not None
            and _annotation_hides_raw_type(f.data_type, f.raw_type)
        ):
            type_comment = " ".join(f.raw_type.split())

        # Map IntrospectedField.data_type to Python type string for Generic subscript.
        # None data_type (unmapped warehouse type) → "Any" so generated code is valid.
        if f.data_type is None or f.data_type.startswith("TODO:"):
            data_type_str = "Any"
        else:
            data_type_str = f.data_type

        field_class = _field_class_for(f.field_type)
        if field_class == "Metric":
            # Decision 2, applied through the shared helper so `--check` decorates a probed
            # annotation by exactly the same rule. See :func:`metric_annotation`.
            data_type_str = metric_annotation(data_type_str)

        fields.append(
            _FieldContext(
                name=f.name,
                field_class=field_class,
                docstring_body=_docstring_body(f.description),
                type_comment=type_comment,
                data_type=data_type_str,
                source_literal=(
                    _python_str_literal(f.source_name) if f.source_name is not None else None
                ),
            )
        )
    return _ModelContext(
        class_name=view.class_name,
        view_literal=_python_str_literal(view.view_name),
        fields=fields,
    )


def _build_import_lines(models: list[_ModelContext]) -> list[str]:
    """
    Derive a generated module's import block from its resolved field annotations.

    Reads ``_FieldContext.data_type`` — the annotation as it will be written — rather
    than ``IntrospectedField.data_type``, so decoration applied during context building
    (metric nullability) cannot desynchronise the annotation from its import.

    Args:
        models: Model contexts already built by :func:`_build_model_context`.

    Returns:
        Import lines in emission order: stdlib imports sorted alphabetically, then
        ``from typing import Any`` when any field needs it, then exactly one
        ``from semolina import ...`` line. Deterministic for a given input, so repeated
        renders are byte-identical.
    """
    annotations = [f.data_type for model in models for f in model.fields]

    lines = sorted(
        {
            import_line
            for prefix, import_line in _STDLIB_MODULE_PREFIXES.items()
            if any(prefix in annotation for annotation in annotations)
        }
    )

    # Split on the union operator so "Any" is matched as a whole annotation token rather
    # than as a substring of some future annotation that merely contains those letters.
    if any("Any" in annotation.replace("|", " ").split() for annotation in annotations):
        lines.append("from typing import Any")

    # One merged ``from semolina import ...`` statement, built from a set. ruff's isort does
    # not merge two separate ``from semolina import`` statements, and ruff ships as the
    # optional codegen-lint extra — so a second statement would ship duplicated-looking
    # output for anyone without it.
    names = set(_SEMOLINA_IMPORT_NAMES)
    names |= {
        name
        for name in _CONDITIONAL_SEMOLINA_IMPORT_NAMES
        if any(name in annotation.replace("|", " ").split() for annotation in annotations)
    }
    lines.append(f"from semolina import {', '.join(sorted(names))}")
    return lines


def render_views(views: list[IntrospectedView]) -> str:
    """
    Render a list of IntrospectedView objects into a single Python source string.

    Emits a shared imports section at the top, followed by one class definition
    per view. The imports are derived from the annotations the fields resolve to,
    so a ``datetime.date`` field pulls in ``import datetime``, a
    ``decimal.Decimal`` field pulls in ``import decimal``, and an unmapped field
    pulls in ``from typing import Any``.

    The returned source string is *not* passed through ruff. Call
    :func:`render_and_format` if you want automatic formatting.

    Args:
        views: List of views to render into Python classes.

    Returns:
        Raw Python source string (not yet formatted by ruff).

    Example:
        .. code-block:: python

            from semolina.codegen.introspector import (
                IntrospectedField,
                IntrospectedView,
            )
            from semolina.codegen.python_renderer import render_views

            view = IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(
                        name="revenue",
                        field_type="metric",
                        data_type="int",
                    )
                ],
            )
            source = render_views([view])
            # 'from semolina import Dimension, Fact, Metric, SemanticView' in source
    """
    # Build the models FIRST: imports are derived from the resolved annotations the
    # template will actually emit, not from the raw introspected types.
    models = [_build_model_context(v) for v in views]
    import_lines = _build_import_lines(models)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,
    )
    template = env.get_template("python_model.py.jinja2")
    return template.render(  # type: ignore[no-any-return]
        models=models,
        import_lines=import_lines,
    )


def ruff_available() -> bool:
    """
    Report whether ruff can be invoked in the current environment.

    ruff ships as the optional ``codegen-lint`` extra. When it is installed,
    :func:`format_with_ruff` produces formatted, import-sorted output; otherwise
    the generated source is returned unchanged.

    Returns:
        True if the ``ruff`` package is importable, False otherwise.
    """
    return importlib.util.find_spec("ruff") is not None


def format_with_ruff(source: str) -> str:
    """
    Format Python source using ruff from the current environment.

    Runs ``ruff format`` followed by ``ruff check --fix --select I`` via
    ``python -m ruff`` (the interpreter running Semolina), so it needs no ``uv``
    or ruff on ``PATH`` -- only the optional ``codegen-lint`` extra installed.
    Falls back gracefully: format failure returns original source; isort failure
    returns formatted-but-unsorted source. When ruff is not installed, the source
    is returned unchanged without spawning either subprocess (see
    :func:`ruff_available`).

    Args:
        source: Python source string to format.

    Returns:
        Formatted and import-sorted Python source if both passes succeed.
        Falls back to formatted source if isort pass fails, or original source
        if format pass fails.
    """
    if not ruff_available():
        # ruff ships as the optional codegen-lint extra. Skip the two subprocess
        # spawns entirely when it is not installed -- they would only exit
        # non-zero and return the original source anyway.
        return source

    try:
        format_result = subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--stdin-filename", "models.py", "-"],
            input=source,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return source

    if format_result.returncode != 0:
        return source

    formatted = format_result.stdout

    try:
        isort_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--fix",
                "--select",
                "I",
                "--stdin-filename",
                "models.py",
                "-",
            ],
            input=formatted,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return formatted

    if isort_result.returncode != 0:
        return formatted

    return isort_result.stdout


def render_and_format(views: list[IntrospectedView]) -> str:
    """
    Render views to Python source and format with ruff.

    Convenience wrapper that calls :func:`render_views` followed by
    :func:`format_with_ruff`. This is what the CLI calls.

    Args:
        views: List of views to render into Python classes.

    Returns:
        Formatted Python source string. Falls back to unformatted source if
        ruff is unavailable or exits non-zero.

    Example:
        .. code-block:: python

            from semolina.codegen.introspector import (
                IntrospectedField,
                IntrospectedView,
            )
            from semolina.codegen.python_renderer import (
                render_and_format,
            )

            view = IntrospectedView(
                view_name="sales_view",
                class_name="SalesView",
                fields=[
                    IntrospectedField(
                        name="revenue",
                        field_type="metric",
                        data_type="int",
                    )
                ],
            )
            source = render_and_format([view])
    """
    return format_with_ruff(render_views(views))
