from collections.abc import Sequence
from typing import Protocol

BATCH_SIZE = 16


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, device: str):
        self.model_name = model_name
        self._device = device
        self._model = None

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._load().encode(list(texts), batch_size=BATCH_SIZE, normalize_embeddings=True)
        return vectors.tolist()

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self._device)
        return self._model
