"""Funil da consulta: filtros → busca híbrida → reranker → limiar → resposta."""

import psycopg

from app.config import Config
from app.ingest.embed import Embedder
from app.search.answer import AnswerRules, build_answer
from app.search.hybrid import HybridSearcher
from app.search.models import ScoredCandidate, SearchFilters
from app.search.rerank import Reranker


class SearchService:
    def __init__(self, embedder: Embedder, reranker: Reranker, config: Config):
        self._embedder = embedder
        self._reranker = reranker
        self._config = config

    def warm_up(self) -> None:
        """Carrega os modelos e roda uma inferência: no MPS a 1ª chamada compila kernels."""
        self._embedder.embed(["aquecimento"])
        self._reranker.score("aquecimento", ["aquecimento"])

    def ask(
        self,
        conn: psycopg.Connection,
        question: str,
        filters: SearchFilters | None = None,
        threshold: float | None = None,
    ) -> dict:
        scored = self.score_candidates(conn, question, filters or SearchFilters())
        rules = AnswerRules(
            threshold=self._config.busca.limiar_reranker if threshold is None else threshold,
            max_results=self._config.busca.top_reranker,
            related_threshold=self._config.busca.limiar_relacionados,
            max_related=self._config.busca.max_relacionados,
        )
        return build_answer(question, scored, rules)

    def score_candidates(
        self, conn: psycopg.Connection, question: str, filters: SearchFilters
    ) -> list[ScoredCandidate]:
        """Separado de `ask` para a avaliação varrer limiares sem repetir busca e reranking."""
        searcher = HybridSearcher(conn, self._embedder, self._config.busca.candidatos, self._config.busca.rrf_k)
        candidates = searcher.search(question, filters)
        scores = self._reranker.score(question, [candidate.texto for candidate in candidates])
        return [ScoredCandidate(candidate, score) for candidate, score in zip(candidates, scores)]


def build_search_service(config: Config) -> SearchService:
    from app.ingest.devices import resolve_device
    from app.ingest.embed import SentenceTransformerEmbedder
    from app.search.rerank import CrossEncoderReranker

    device = resolve_device(config.modelos.device)
    return SearchService(
        SentenceTransformerEmbedder(config.modelos.embedding, device),
        CrossEncoderReranker(config.modelos.reranker, device),
        config,
    )
