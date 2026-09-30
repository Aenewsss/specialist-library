"""Transcrição: legenda do YouTube ou Whisper sobre o áudio, conforme a preferência."""
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import CouldNotRetrieveTranscript

from app.ingest.audio import load_mono_16k
from app.ingest.models import Segment


class TranscriptUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Transcript:
    segments: list[Segment]
    origin: str  # 'legenda_youtube' | 'whisper'


class YoutubeCaptionSource:
    def __init__(self, languages: Sequence[str]):
        self._languages = list(languages)
        self._api = YouTubeTranscriptApi()

    def fetch(self, video_id: str) -> Transcript:
        try:
            fetched = self._api.fetch(video_id, languages=self._languages)
        except CouldNotRetrieveTranscript as error:
            raise TranscriptUnavailable(str(error)) from error
        raw = [Segment(s.start, s.start + s.duration, s.text) for s in fetched.snippets]
        return Transcript(segments=trim_rolling_overlaps(raw), origin="legenda_youtube")


def trim_rolling_overlaps(segments: Sequence[Segment]) -> list[Segment]:
    """Legenda automática "rola": cada linha ainda está na tela quando a próxima começa.
    Corta o fim de cada linha no início da seguinte para os tempos não se sobreporem."""
    trimmed = []
    for current, following in zip(segments, [*segments[1:], None]):
        end = min(current.end, following.start) if following else current.end
        trimmed.append(Segment(current.start, max(end, current.start), current.text))
    return trimmed


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> Transcript: ...


@dataclass(frozen=True)
class TimedWord:
    start: float
    end: float
    text: str


MAX_PIECE_S = 3.0  # mesma ordem de grandeza de uma linha de legenda
PAUSE_BREAK_S = 0.5


def group_words(words: Sequence[TimedWord], max_piece_s: float = MAX_PIECE_S) -> list[Segment]:
    """Whisper devolve frases longas que podem atravessar uma troca de falante. Reagrupa as
    palavras em pedaços curtos, fechando em fim de frase, pausa ou tamanho máximo, para a
    atribuição de falante trabalhar na mesma granularidade da legenda."""
    pieces: list[Segment] = []
    current: list[TimedWord] = []
    for word, following in zip(words, [*words[1:], None]):
        current.append(word)
        if following is None or _closes_piece(current, following, max_piece_s):
            pieces.append(Segment(current[0].start, current[-1].end, "".join(w.text for w in current).strip()))
            current = []
    return pieces


def _closes_piece(current: list[TimedWord], following: TimedWord, max_piece_s: float) -> bool:
    ends_sentence = current[-1].text.rstrip().endswith((".", "?", "!"))
    long_pause = following.start - current[-1].end >= PAUSE_BREAK_S
    too_long = following.end - current[0].start > max_piece_s
    return ends_sentence or long_pause or too_long


class WhisperTranscriber:
    def __init__(self, model_name: str, language: str):
        self._model_name = model_name
        self._language = language
        self._model = None

    def transcribe(self, audio_path: Path) -> Transcript:
        segments, _ = self._load().transcribe(
            load_mono_16k(audio_path), language=self._language, vad_filter=True, word_timestamps=True
        )
        words = [TimedWord(w.start, w.end, w.word) for segment in segments for w in segment.words]
        return Transcript(group_words(words), origin="whisper")

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            # CTranslate2 não usa Metal: no Mac roda em CPU quantizado, com todos os núcleos.
            self._model = WhisperModel(
                self._model_name, device="auto", compute_type="int8", cpu_threads=os.cpu_count() or 4
            )
        return self._model


def transcribe_video(
    video_id: str,
    captions: YoutubeCaptionSource,
    whisper: Transcriber,
    get_audio: Callable[[], Path],
    prefer: str = "legenda_youtube",
) -> Transcript:
    """Com preferência por legenda, o Whisper só entra se o vídeo não tiver legenda."""
    if prefer == "whisper":
        return whisper.transcribe(get_audio())
    try:
        return captions.fetch(video_id)
    except TranscriptUnavailable:
        return whisper.transcribe(get_audio())
