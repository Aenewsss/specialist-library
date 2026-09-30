from dataclasses import dataclass, field
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class SearchFilters:
    pessoa_ids: list[UUID] = field(default_factory=list)
    area: str | None = None
    published_from: date | None = None
    published_until: date | None = None
    fonte_tipos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    """Um trecho candidato, com tudo o que a resposta precisa exibir."""
    trecho_id: UUID
    texto: str
    inicio_s: int | None
    fim_s: int | None
    pagina: int | None
    pessoa_id: UUID
    pessoa_nome: str
    pessoa_areas: list[str]
    conteudo_titulo: str | None
    publicado_em: date | None
    url_original: str
    external_id: str | None
    fonte_tipo: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
