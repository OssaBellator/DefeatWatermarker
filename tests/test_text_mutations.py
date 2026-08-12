from defeat_watermarker.models import Artifact, Modality, MutationScenario
from defeat_watermarker.mutations.text import (
    NormalizeLineEndingsLf,
    NormalizeUnicodeNfc,
    StripTrailingHorizontalWhitespace,
)


def _scenario(mutation_id: str) -> MutationScenario:
    return MutationScenario(
        scenario_id="fixture",
        mutation_id=mutation_id,
        modality=Modality.TEXT,
        transformation_family="fixture",
    )


def _artifact(text: str) -> Artifact:
    return Artifact(
        data=text.encode("utf-8"),
        media_type="text/plain",
        modality=Modality.TEXT,
    )


def test_unicode_nfc_normalizes_combining_form() -> None:
    source = _artifact("Cafe\u0301")
    result = NormalizeUnicodeNfc().apply(source, _scenario(NormalizeUnicodeNfc.mutation_id))
    assert result.data.decode("utf-8") == "Café"


def test_line_endings_are_normalized_without_rewriting_words() -> None:
    source = _artifact("one\r\ntwo\rthree\n")
    result = NormalizeLineEndingsLf().apply(
        source, _scenario(NormalizeLineEndingsLf.mutation_id)
    )
    assert result.data.decode("utf-8") == "one\ntwo\nthree\n"


def test_trailing_spaces_and_tabs_are_removed() -> None:
    source = _artifact("one  \n two\t\n")
    result = StripTrailingHorizontalWhitespace().apply(
        source, _scenario(StripTrailingHorizontalWhitespace.mutation_id)
    )
    assert result.data.decode("utf-8") == "one\n two\n"
