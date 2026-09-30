"""Atribuição de fala: quem falou cada segmento e a quem pertence cada voz."""
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

import numpy as np

from app.ingest.models import Segment, SpeakerTurn


def assign_speakers(segments: Sequence[Segment], turns: Sequence[SpeakerTurn]) -> list[Segment]:
    """Marca cada segmento com o falante de maior sobreposição de tempo (None se nenhum)."""
    return [segment.with_speaker(_dominant_speaker(segment, turns)) for segment in segments]


def _dominant_speaker(segment: Segment, turns: Sequence[SpeakerTurn]) -> str | None:
    overlap_by_speaker: dict[str, float] = {}
    for turn in turns:
        overlap = turn.overlap_with(segment.start, segment.end)
        if overlap > 0:
            overlap_by_speaker[turn.speaker] = overlap_by_speaker.get(turn.speaker, 0.0) + overlap
    if not overlap_by_speaker:
        return None
    return max(overlap_by_speaker, key=overlap_by_speaker.get)


@dataclass(frozen=True)
class VoiceMatch:
    pessoa_id: UUID | None
    similarity: float | None


def match_voice(
    voice: Sequence[float],
    samples_by_pessoa: Mapping[UUID, Iterable[Sequence[float]]],
    threshold: float,
) -> VoiceMatch:
    """Compara a voz com as amostras confirmadas; abaixo do limiar, não atribui."""
    best_pessoa, best_similarity = None, None
    for pessoa_id, samples in samples_by_pessoa.items():
        similarity = max(cosine_similarity(voice, sample) for sample in samples)
        if best_similarity is None or similarity > best_similarity:
            best_pessoa, best_similarity = pessoa_id, similarity
    if best_similarity is None or best_similarity < threshold:
        return VoiceMatch(pessoa_id=None, similarity=best_similarity)
    return VoiceMatch(pessoa_id=best_pessoa, similarity=best_similarity)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))
