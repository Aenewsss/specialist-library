from collections.abc import Sequence
from typing import Protocol


class Reranker(Protocol):
    model_name: str

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        """Relevância de cada trecho para a pergunta, em [0, 1]."""
        ...


class CrossEncoderReranker:
    """Cross-encoder: lê pergunta e trecho juntos, por isso separa tema de resposta melhor que o embedding."""

    def __init__(self, model_name: str, device: str):
        self.model_name = model_name
        self._device = device
        self._model = None

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        scores = self._load().predict([(question, passage) for passage in passages])
        return [float(score) for score in scores]

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            # Com um único rótulo de saída, o CrossEncoder aplica sigmoide: notas em [0, 1].
            self._model = CrossEncoder(self.model_name, device=self._device)
        return self._model
