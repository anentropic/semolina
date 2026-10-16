"""
D9's type comparison: two annotations compare by the type they name, not their spelling.

Every test resolves names through a plain dict standing in for a committed file's imports,
so what is pinned is the reduction itself. Reading the imports out of a real file is
``test_model_reader.py``'s and ``test_dto_reader.py``'s job.
"""

from __future__ import annotations

import pytest

from semolina.codegen.type_compare import canonical_annotation, generated_annotation

IMPORTS = {
    "Optional": "typing.Optional",
    "Union": "typing.Union",
    "Annotated": "typing.Annotated",
    "Literal": "typing.Literal",
    "List": "typing.List",
    "typing": "typing",
    "Decimal": "decimal.Decimal",
    "decimal": "decimal",
    "datetime": "datetime",
    "JsonValue": "semolina.JsonValue",
    "types": "semolina.types",
    "pydantic": "pydantic",
    "Money": "app.types.Money",
}
"""What a committed file's imports might bind, by name."""


class TestEquivalentSpellingsAgree:
    """Each spelling of one type reduces to codegen's spelling of it."""

    @pytest.mark.parametrize(
        "annotation",
        [
            "decimal.Decimal | None",
            "None | decimal.Decimal",
            "Optional[decimal.Decimal]",
            "Optional[Decimal]",
            "Union[Decimal, None]",
            "typing.Optional[Decimal]",
            "'decimal.Decimal | None'",
            "Optional['Decimal']",
            "Annotated[Decimal | None, pydantic.Field(description='x')]",
        ],
    )
    def test_an_optional_decimal(self, annotation: str) -> None:
        assert canonical_annotation(annotation, IMPORTS.get) == "decimal.Decimal | None"

    def test_a_builtin_needs_no_import(self) -> None:
        assert canonical_annotation("'str'", IMPORTS.get) == "str"

    def test_a_typing_alias_reads_as_the_builtin_generic(self) -> None:
        assert canonical_annotation("List[int]", IMPORTS.get) == "list[int]"

    @pytest.mark.parametrize("annotation", ["JsonValue", "types.JsonValue"])
    def test_json_value_by_either_import_path(self, annotation: str) -> None:
        assert canonical_annotation(annotation, IMPORTS.get) == "JsonValue"

    def test_a_union_of_three_is_order_independent(self) -> None:
        assert canonical_annotation("None | str | int", IMPORTS.get) == canonical_annotation(
            "Union[int, str, None]", IMPORTS.get
        )


class TestDifferentTypesStayDifferent:
    """The reduction never makes two different types compare equal."""

    def test_a_dropped_none_is_not_optional(self) -> None:
        assert canonical_annotation("Decimal", IMPORTS.get) == "decimal.Decimal"

    def test_int_is_not_decimal(self) -> None:
        assert canonical_annotation("Optional[int]", IMPORTS.get) == "int | None"

    def test_datetime_and_date_are_different(self) -> None:
        assert canonical_annotation("datetime.date", IMPORTS.get) != canonical_annotation(
            "datetime.datetime", IMPORTS.get
        )


class TestWhatIsNotComparedByMeaning:
    """Anything outside the allowlist or the grammar gives up, so the text is compared."""

    def test_a_users_own_type(self) -> None:
        assert canonical_annotation("Money | None", IMPORTS.get) is None

    def test_an_unknown_name(self) -> None:
        assert canonical_annotation("Mystery", IMPORTS.get) is None

    def test_literal_strings_are_values_not_forward_references(self) -> None:
        assert canonical_annotation("Literal['int']", IMPORTS.get) is None

    def test_a_call_is_never_evaluated(self) -> None:
        assert canonical_annotation("make_type()", IMPORTS.get) is None

    def test_text_that_does_not_parse(self) -> None:
        assert canonical_annotation("int |", IMPORTS.get) is None

    def test_annotated_with_no_arguments(self) -> None:
        assert canonical_annotation("Annotated[()]", IMPORTS.get) is None


class TestTheGeneratedSide:
    """Codegen's own annotations come back unchanged."""

    @pytest.mark.parametrize(
        "annotation",
        [
            "decimal.Decimal | None",
            "int",
            "str | None",
            "Any",
            "Any | None",
            "JsonValue",
            "datetime.datetime | None",
            "bytes",
        ],
    )
    def test_codegen_spelling_is_a_fixed_point(self, annotation: str) -> None:
        assert generated_annotation(annotation) == annotation
