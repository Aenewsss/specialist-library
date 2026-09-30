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
    related_threshold: float | None = None  # None desliga os relacionados
    max_related: int = 3


def build_answer(question: str, scored: Sequence[ScoredCandidate], rules: AnswerRules) -> dict:
    """Acima do limiar: resposta direta. Sem resposta direta, trechos entre os dois limiares
    voltam à parte como relacionados, para a interface marcar como baixa confiança em vez de
    apresentá-los como resposta."""
    ranked = sorted(scored, key=lambda item: item.score, reverse=True)
    kept = [item for item in ranked if item.score >= rules.threshold][: rules.max_results]
    related = [] if kept else _related(ranked, rules)
    return {
        "pergunta": question,
        "encontrado": bool(kept),
        "resultados": _group_by_pessoa(kept),
        "relacionados": _group_by_pessoa(related),
    }


def _related(ranked: Sequence[ScoredCandidate], rules: AnswerRules) -> list[ScoredCandidate]:
    if rules.related_threshold is None:
        return []
    return [item for item in ranked if item.score >= rules.related_threshold][: rules.max_related]


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
