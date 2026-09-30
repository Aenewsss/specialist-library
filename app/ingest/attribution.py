"""Atribuição automática de vozes a pessoas, pelas amostras de voz confirmadas.

Roda na ingestão (etapa 'atribuicao') e de novo sempre que uma voz é confirmada,
porque cada confirmação vira uma amostra nova que pode reconhecer vozes pendentes."""
from dataclasses import dataclass
from uuid import UUID

import psycopg

from app.config import Config
from app.ingest import repository
from app.ingest.attribute import VoiceMatch, match_voice


@dataclass(frozen=True)
class AttributionRules:
    voice_threshold: float
    min_speaking_seconds: float


def attribution_rules(config: Config) -> AttributionRules:
    return AttributionRules(
        voice_threshold=config.atribuicao.limiar_voz, min_speaking_seconds=config.atribuicao.min_segundos_fala
    )


def attribute_conteudo(conn: psycopg.Connection, conteudo_id: UUID, rules: AttributionRules) -> int:
    """Reavalia as vozes não confirmadas do conteúdo. Devolve quantas vozes sem autor ganharam um."""
    samples = repository.voice_samples_by_pessoa(conn)
    newly_attributed = 0
    with conn.transaction():
        for speaker in repository.unconfirmed_speakers(conn, conteudo_id):
            match = _match(speaker, samples, rules)
            repository.set_speaker_attribution(conn, conteudo_id, speaker.label, match.pessoa_id, match.similarity)
            newly_attributed += speaker.current_pessoa_id is None and match.pessoa_id is not None
        repository.sync_trecho_pessoas(conn, conteudo_id)
    return newly_attributed


def attribute_all_pending(conn: psycopg.Connection, rules: AttributionRules) -> int:
    """Reavalia todo conteúdo que ainda tem voz não confirmada."""
    rows = conn.execute(
        "SELECT DISTINCT conteudo_id FROM falante_conteudo WHERE NOT confirmado AND NOT ignorado"
    ).fetchall()
    return sum(attribute_conteudo(conn, row["conteudo_id"], rules) for row in rows)


def _match(speaker: repository.UnconfirmedSpeaker, samples, rules: AttributionRules) -> VoiceMatch:
    """Pouca fala gera vetor de voz pouco confiável: fica sem autor e vai para revisão."""
    if speaker.speaking_seconds < rules.min_speaking_seconds:
        return VoiceMatch(pessoa_id=None, similarity=None)
    return match_voice(speaker.voice, samples, rules.voice_threshold)
