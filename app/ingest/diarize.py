"""Diarização: quem fala quando, com falantes anônimos (SPEAKER_00…)."""
import os
from pathlib import Path
from typing import Protocol

from app.ingest.attribute import is_valid_voice
from app.ingest.audio import SAMPLE_RATE, load_mono_16k
from app.ingest.models import Diarization, SpeakerTurn


class Diarizer(Protocol):
    def diarize(self, audio_path: Path) -> Diarization: ...


class MissingHuggingFaceToken(RuntimeError):
    pass


class PyannoteDiarizer:
    def __init__(self, model_name: str, device: str):
        self._model_name = model_name
        self._device = device
        self._pipeline = None

    def diarize(self, audio_path: Path) -> Diarization:
        import torch

        waveform = torch.from_numpy(load_mono_16k(audio_path)).unsqueeze(0)
        output = self._load()({"waveform": waveform, "sample_rate": SAMPLE_RATE})
        # A versão exclusiva não tem fala sobreposta: cada instante tem um só falante.
        turns = [
            SpeakerTurn(round(segment.start, 2), round(segment.end, 2), label)
            for segment, _, label in output.exclusive_speaker_diarization.itertracks(yield_label=True)
        ]
        labels = output.speaker_diarization.labels()
        embeddings = {
            label: _valid_or_none(output.speaker_embeddings[index].tolist()) for index, label in enumerate(labels)
        }
        return Diarization(turns=turns, voice_embeddings=embeddings)

    def _load(self):
        if self._pipeline is None:
            import torch
            from pyannote.audio import Pipeline

            token = os.environ.get("HF_TOKEN")
            if not token:
                raise MissingHuggingFaceToken("Defina HF_TOKEN no .env (modelo do pyannote exige aceite de termos)")
            self._pipeline = Pipeline.from_pretrained(self._model_name, token=token)
            self._pipeline.to(torch.device(self._device))
        return self._pipeline


def _valid_or_none(voice: list[float]) -> list[float] | None:
    return voice if is_valid_voice(voice) else None
