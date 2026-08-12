from __future__ import annotations

import re
import unicodedata

from ..models import Artifact, Modality, MutationScenario
from .base import ArtifactMutation


class TextMutationError(ValueError):
    """Raised when a fixed text editorial transformation cannot be applied."""


def _decode_text(artifact: Artifact) -> str:
    if artifact.modality not in {Modality.TEXT, Modality.UNKNOWN}:
        raise TextMutationError("text mutation requires a text artifact")
    try:
        return artifact.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TextMutationError("text mutation requires valid UTF-8") from exc


def _text_artifact(source: Artifact, text: str) -> Artifact:
    return Artifact(
        data=text.encode("utf-8"),
        media_type=source.media_type if source.media_type.startswith("text/") else "text/plain",
        name=source.name,
        modality=Modality.TEXT,
    )


class NormalizeUnicodeNfc(ArtifactMutation):
    """Apply Unicode NFC normalization without semantic rewriting."""

    mutation_id = "text.unicode-nfc.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        return _text_artifact(artifact, unicodedata.normalize("NFC", _decode_text(artifact)))


class NormalizeLineEndingsLf(ArtifactMutation):
    """Normalize CRLF/CR line endings to LF."""

    mutation_id = "text.line-endings-lf.v1"

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        text = _decode_text(artifact).replace("\r\n", "\n").replace("\r", "\n")
        return _text_artifact(artifact, text)


class StripTrailingHorizontalWhitespace(ArtifactMutation):
    """Remove spaces/tabs at line ends, matching ordinary editor cleanup."""

    mutation_id = "text.strip-trailing-horizontal-whitespace.v1"
    _TRAILING = re.compile(r"[ \t]+(?=\r?$)", re.MULTILINE)

    def apply(self, artifact: Artifact, scenario: MutationScenario) -> Artifact:
        return _text_artifact(artifact, self._TRAILING.sub("", _decode_text(artifact)))
