"""Revisão humana de falantes: ouvir amostras e dizer quem é cada voz."""
from dataclasses import dataclass
from uuid import UUID

import psycopg

from app.ingest import repository
from app.search.links import SourcePosition, build_link

SAMPLE_TURNS_PER_SPEAKER = 3
MIN_SAMPLE_TURN_S = 8  # turnos curtos demais não ajudam a reconhecer a voz


class SpeakerNotFound(LookupError):
    pass


@dataclass(frozen=True)
class SpeakerSummary:
    label: str
    speaking_seconds: float
    pessoa_nome: str | None
    confidence: float | None
    confirmed: bool
    ignored: bool
    sample_links: list[str]


def list_speakers(conn: psycopg.Connection, conteudo_id: UUID) -> list[SpeakerSummary]:
    conteudo = repository.get_conteudo(conn, conteudo_id)
    rows = conn.execute(
        "SELECT f.rotulo, f.segundos_fala, f.confianca_atribuicao, f.confirmado, f.ignorado, p.nome"
        " FROM falante_conteudo f LEFT JOIN pessoa p ON p.id = f.pessoa_id"
        " WHERE f.conteudo_id = %s ORDER BY f.segundos_fala DESC",
        (conteudo_id,),
    ).fetchall()
    return [
        SpeakerSummary(
            label=row["rotulo"],
            speaking_seconds=row["segundos_fala"],
            pessoa_nome=row["nome"],
            confidence=row["confianca_atribuicao"],
            confirmed=row["confirmado"],
            ignored=row["ignorado"],
            sample_links=_sample_links(conteudo, row["rotulo"]),
        )
        for row in rows
    ]


def _sample_links(conteudo: repository.ConteudoRecord, label: str) -> list[str]:
    turns = [turn for turn in conteudo.turns if turn.speaker == label]
    long_enough = [turn for turn in turns if turn.end - turn.start >= MIN_SAMPLE_TURN_S] or turns
    longest = sorted(long_enough, key=lambda turn: turn.end - turn.start, reverse=True)
    chosen = sorted(longest[:SAMPLE_TURNS_PER_SPEAKER], key=lambda turn: turn.start)
    return [
        build_link(SourcePosition(conteudo.fonte_tipo, "", conteudo.external_id, start_s=int(turn.start)))
        for turn in chosen
    ]


def confirm_speaker(conn: psycopg.Connection, conteudo_id: UUID, label: str, pessoa_id: UUID) -> None:
    """Confirma a voz como da pessoa, guarda a voz como amostra para os próximos conteúdos
    e atualiza a autoria dos trechos deste conteúdo."""
    with conn.transaction():
        updated = conn.execute(
            "UPDATE falante_conteudo SET pessoa_id = %s, confianca_atribuicao = 1.0, confirmado = true"
            ", ignorado = false"
            " WHERE conteudo_id = %s AND rotulo = %s RETURNING embedding_voz",
            (pessoa_id, conteudo_id, label),
        ).fetchone()
        if updated is None:
            raise SpeakerNotFound(f"Falante {label} não existe nesse conteúdo")
        conn.execute(
            "INSERT INTO amostra_voz (pessoa_id, embedding_voz, origem_conteudo_id, origem_rotulo)"
            " SELECT %s, embedding_voz, conteudo_id, rotulo FROM falante_conteudo"
            " WHERE conteudo_id = %s AND rotulo = %s AND embedding_voz IS NOT NULL"
            " ON CONFLICT (origem_conteudo_id, origem_rotulo) DO UPDATE SET pessoa_id = EXCLUDED.pessoa_id",
            (pessoa_id, conteudo_id, label),
        )
        repository.sync_trecho_pessoas(conn, conteudo_id)


def ignore_speaker(conn: psycopg.Connection, conteudo_id: UUID, label: str) -> int:
    """Descarta a voz (ex.: apresentador): apaga os trechos dela e impede que voltem ao re-fatiar.
    Devolve quantos trechos foram removidos."""
    with conn.transaction():
        updated = conn.execute(
            "UPDATE falante_conteudo SET ignorado = true, confirmado = true, pessoa_id = NULL,"
            " confianca_atribuicao = NULL WHERE conteudo_id = %s AND rotulo = %s RETURNING rotulo",
            (conteudo_id, label),
        ).fetchone()
        if updated is None:
            raise SpeakerNotFound(f"Falante {label} não existe nesse conteúdo")
        removed = conn.execute(
            "DELETE FROM trecho WHERE conteudo_id = %s AND falante_rotulo = %s", (conteudo_id, label)
        ).rowcount
    return removed
