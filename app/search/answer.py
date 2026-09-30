"""Monta a resposta a partir de trechos já pontuados. Nenhum texto é gerado aqui:
tudo o que sai é texto gravado no banco, mais o link montado a partir da posição."""
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.search.links import SourcePosition, build_link
from app.search.models import Candidate, ScoredCandidate


@dataclass(frozen=True)
class AnswerRules:
    threshold: float
    max_results: int


def build_answer(question: str, scored: Sequence[ScoredCandidate], rules: AnswerRules) -> dict:
    kept = sorted((s for s in scored if s.score >= rules.threshold), key=lambda s: s.score, reverse=True)
    kept = kept[: rules.max_results]
    return {
        "pergunta": question,
        "encontrado": bool(kept),
        "resultados": _group_by_pessoa(kept),
    }


def _group_by_pessoa(kept: Sequence[ScoredCandidate]) -> list[dict]:
    """Pessoas na ordem do melhor trecho de cada uma; trechos por nota dentro de cada pessoa."""
    groups: dict[UUID, dict] = {}
    for item in kept:
        candidate = item.candidate
        group = groups.setdefault(candidate.pessoa_id, {"pessoa": _pessoa(candidate), "trechos": []})
        group["trechos"].append(_trecho(item))
    return list(groups.values())


def _pessoa(candidate: Candidate) -> dict:
    return {"id": str(candidate.pessoa_id), "nome": candidate.pessoa_nome, "areas": candidate.pessoa_areas}


def _trecho(item: ScoredCandidate) -> dict:
    candidate = item.candidate
    position = SourcePosition(
        fonte_tipo=candidate.fonte_tipo,
        url_original=candidate.url_original,
        external_id=candidate.external_id,
        start_s=candidate.inicio_s,
        page=candidate.pagina,
    )
    return {
        "trecho_id": str(candidate.trecho_id),
        "texto": candidate.texto,
        "conteudo_titulo": candidate.conteudo_titulo,
        "publicado_em": candidate.publicado_em.isoformat() if candidate.publicado_em else None,
        "inicio_s": candidate.inicio_s,
        "fim_s": candidate.fim_s,
        "link": build_link(position),
        "nota_reranker": round(item.score, 4),
    }
