"""Busca híbrida: vetorial (significado) + full-text (termos exatos), unidas por RRF."""
from collections.abc import Sequence
from uuid import UUID

import psycopg

from app.ingest.embed import Embedder
from app.search.models import Candidate, SearchFilters


def reciprocal_rank_fusion(rankings: Sequence[Sequence[UUID]], k: int) -> list[UUID]:
    """Cada lista contribui 1/(k + posição). Não depende da escala das notas de cada busca."""
    scores: dict[UUID, float] = {}
    for ranking in rankings:
        for position, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + position)
    return sorted(scores, key=scores.get, reverse=True)


def build_filter_clause(filters: SearchFilters) -> tuple[str, dict]:
    """Filtros viram WHERE aplicados antes da busca. Trecho sem autor nunca é exibido."""
    clauses, params = ["t.pessoa_id IS NOT NULL"], {}
    if filters.pessoa_ids:
        clauses.append("t.pessoa_id = ANY(%(pessoa_ids)s)")
        params["pessoa_ids"] = list(filters.pessoa_ids)
    if filters.area:
        clauses.append(
            "EXISTS (SELECT 1 FROM pessoa_area pa JOIN area a ON a.id = pa.area_id"
            " WHERE pa.pessoa_id = t.pessoa_id AND a.nome = %(area)s)"
        )
        params["area"] = filters.area
    if filters.published_from:
        clauses.append("c.publicado_em >= %(published_from)s")
        params["published_from"] = filters.published_from
    if filters.published_until:
        clauses.append("c.publicado_em <= %(published_until)s")
        params["published_until"] = filters.published_until
    if filters.fonte_tipos:
        clauses.append("f.tipo = ANY(%(fonte_tipos)s)")
        params["fonte_tipos"] = list(filters.fonte_tipos)
    return " AND ".join(clauses), params


FROM_TRECHO = " FROM trecho t JOIN conteudo c ON c.id = t.conteudo_id JOIN fonte f ON f.id = c.fonte_id"

CANDIDATE_COLUMNS = """
  t.id AS trecho_id, t.texto, t.inicio_s, t.fim_s, t.pagina,
  t.pessoa_id, p.nome AS pessoa_nome,
  ARRAY(SELECT a.nome FROM pessoa_area pa JOIN area a ON a.id = pa.area_id
        WHERE pa.pessoa_id = p.id ORDER BY a.nome) AS pessoa_areas,
  c.titulo AS conteudo_titulo, c.publicado_em, c.url_original, c.id_externo AS external_id,
  f.tipo AS fonte_tipo
"""


class HybridSearcher:
    def __init__(self, conn: psycopg.Connection, embedder: Embedder, candidate_limit: int, rrf_k: int):
        self._conn = conn
        self._embedder = embedder
        self._limit = candidate_limit
        self._rrf_k = rrf_k

    def search(self, question: str, filters: SearchFilters) -> list[Candidate]:
        where, params = build_filter_clause(filters)
        vector_ids = self._vector_search(question, where, params)
        text_ids = self._fulltext_search(question, where, params)
        fused = reciprocal_rank_fusion([vector_ids, text_ids], self._rrf_k)[: self._limit]
        return self._load_candidates(fused)

    def _vector_search(self, question: str, where: str, params: dict) -> list[UUID]:
        [query_vector] = self._embedder.embed([question])
        rows = self._conn.execute(
            f"SELECT t.id {FROM_TRECHO} WHERE t.embedding IS NOT NULL AND {where}"
            " ORDER BY t.embedding <=> %(query_vector)s::vector LIMIT %(limit)s",
            {**params, "query_vector": str(query_vector), "limit": self._limit},
        )
        return [row["id"] for row in rows]

    def _fulltext_search(self, question: str, where: str, params: dict) -> list[UUID]:
        any_term_query = self._any_term_tsquery(question)
        if not any_term_query:
            return []
        rows = self._conn.execute(
            f"SELECT t.id {FROM_TRECHO} WHERE t.busca_texto @@ %(tsquery)s::tsquery AND {where}"
            " ORDER BY ts_rank_cd(t.busca_texto, %(tsquery)s::tsquery) DESC LIMIT %(limit)s",
            {**params, "tsquery": any_term_query, "limit": self._limit},
        )
        return [row["id"] for row in rows]

    def _any_term_tsquery(self, question: str) -> str:
        """Pergunta em linguagem natural tem palavras que o trecho não contém ("diz", "opinião").
        Com E entre os termos (websearch_to_tsquery) quase nada casaria; com OU, o ranking decide."""
        all_terms = self._conn.execute(
            "SELECT plainto_tsquery('portuguese', %s)::text AS q", (question,)
        ).fetchone()["q"]
        return all_terms.replace(" & ", " | ")

    def _load_candidates(self, trecho_ids: list[UUID]) -> list[Candidate]:
        if not trecho_ids:
            return []
        rows = self._conn.execute(
            f"SELECT {CANDIDATE_COLUMNS} {FROM_TRECHO} JOIN pessoa p ON p.id = t.pessoa_id"
            " WHERE t.id = ANY(%s)",
            (trecho_ids,),
        ).fetchall()
        by_id = {row["trecho_id"]: Candidate(**row) for row in rows}
        return [by_id[trecho_id] for trecho_id in trecho_ids if trecho_id in by_id]
