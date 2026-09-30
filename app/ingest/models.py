"""Tipos do domínio de ingestão, sem dependência de banco ou de modelo."""
from dataclasses import asdict, dataclass, replace
from datetime import date


@dataclass(frozen=True)
class Segment:
    """Uma linha de transcrição com timestamps (em segundos)."""
    start: float
    end: float
    text: str
    speaker: str | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    def with_speaker(self, speaker: str | None) -> "Segment":
        return replace(self, speaker=speaker)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str

    def overlap_with(self, start: float, end: float) -> float:
        return max(0.0, min(self.end, end) - max(self.start, start))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Diarization:
    turns: list[SpeakerTurn]
    voice_embeddings: dict[str, list[float] | None]  # rótulo → vetor de voz (None se inválido)


@dataclass(frozen=True)
class Chunk:
    start: float
    end: float
    text: str
    speaker: str | None


@dataclass(frozen=True)
class ContentMetadata:
    title: str
    published_on: date | None


# Ordem das etapas. Diarização entrou no MVP porque o vídeo-alvo é um debate.
PIPELINE_STAGES = ("coleta", "transcricao", "diarizacao", "atribuicao", "chunking", "embeddings")
