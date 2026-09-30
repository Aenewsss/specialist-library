"""Leitura e escrita do pipeline de ingestão no Postgres."""
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.ingest.models import Chunk, ContentMetadata, Diarization, Segment, SpeakerTurn


@dataclass(frozen=True)
class ConteudoRecord:
    id: UUID
    fonte_tipo: str
    external_id: str
    segments: list[Segment]
    turns: list[SpeakerTurn]


def get_conteudo(conn: psycopg.Connection, conteudo_id: UUID) -> ConteudoRecord:
    row = conn.execute(
        "SELECT c.id, f.tipo, c.id_externo, c.transcricao_bruta, c.diarizacao"
        " FROM conteudo c JOIN fonte f ON f.id = c.fonte_id WHERE c.id = %s",
        (conteudo_id,),
    ).fetchone()
    return ConteudoRecord(
        id=row["id"],
        fonte_tipo=row["tipo"],
        external_id=row["id_externo"],
        segments=[Segment(**segment) for segment in row["transcricao_bruta"] or []],
        turns=[SpeakerTurn(**turn) for turn in row["diarizacao"] or []],
    )


def save_metadata(conn: psycopg.Connection, conteudo_id: UUID, metadata: ContentMetadata) -> None:
    conn.execute(
        "UPDATE conteudo SET titulo = %s, publicado_em = %s WHERE id = %s",
        (metadata.title, metadata.published_on, conteudo_id),
    )


def save_transcript(conn: psycopg.Connection, conteudo_id: UUID, segments: list[Segment], origin: str) -> None:
    conn.execute(
        "UPDATE conteudo SET transcricao_bruta = %s, transcricao_origem = %s WHERE id = %s",
        (Jsonb([segment.to_dict() for segment in segments]), origin, conteudo_id),
    )


def save_diarization(conn: psycopg.Connection, conteudo_id: UUID, diarization: Diarization) -> None:
    """Substitui turnos e falantes. Rodar de novo invalida rótulos anteriores (os SPEAKER_xx mudam)."""
    conn.execute(
        "UPDATE conteudo SET diarizacao = %s WHERE id = %s",
        (Jsonb([turn.to_dict() for turn in diarization.turns]), conteudo_id),
    )
    conn.execute("DELETE FROM falante_conteudo WHERE conteudo_id = %s", (conteudo_id,))
    seconds_by_speaker = _speaking_seconds(diarization.turns)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO falante_conteudo (conteudo_id, rotulo, embedding_voz, segundos_fala)"
            " VALUES (%s, %s, %s::vector, %s)",
            [
                (conteudo_id, label, str(embedding), seconds_by_speaker.get(label, 0.0))
                for label, embedding in diarization.voice_embeddings.items()
            ],
        )


def _speaking_seconds(turns: list[SpeakerTurn]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for turn in turns:
        totals[turn.speaker] += turn.end - turn.start
    return dict(totals)


@dataclass(frozen=True)
class UnconfirmedSpeaker:
    label: str
    voice: list[float]


def unconfirmed_speakers(conn: psycopg.Connection, conteudo_id: UUID) -> list[UnconfirmedSpeaker]:
    rows = conn.execute(
        "SELECT rotulo, embedding_voz::text AS voz FROM falante_conteudo"
        " WHERE conteudo_id = %s AND NOT confirmado AND NOT ignorado AND embedding_voz IS NOT NULL",
        (conteudo_id,),
    ).fetchall()
    return [UnconfirmedSpeaker(row["rotulo"], _parse_vector(row["voz"])) for row in rows]


def voice_samples_by_pessoa(conn: psycopg.Connection) -> dict[UUID, list[list[float]]]:
    rows = conn.execute("SELECT pessoa_id, embedding_voz::text AS voz FROM amostra_voz").fetchall()
    samples: dict[UUID, list[list[float]]] = defaultdict(list)
    for row in rows:
        samples[row["pessoa_id"]].append(_parse_vector(row["voz"]))
    return dict(samples)


def set_speaker_attribution(
    conn: psycopg.Connection, conteudo_id: UUID, label: str, pessoa_id: UUID | None, confidence: float | None
) -> None:
    conn.execute(
        "UPDATE falante_conteudo SET pessoa_id = %s, confianca_atribuicao = %s"
        " WHERE conteudo_id = %s AND rotulo = %s",
        (pessoa_id, confidence, conteudo_id, label),
    )


def sync_trecho_pessoas(conn: psycopg.Connection, conteudo_id: UUID) -> None:
    """Propaga a atribuição dos falantes para os trechos já fatiados."""
    conn.execute(
        "UPDATE trecho t SET pessoa_id = f.pessoa_id, confianca_atribuicao = f.confianca_atribuicao,"
        " revisado = f.confirmado"
        " FROM falante_conteudo f"
        " WHERE t.conteudo_id = %s AND f.conteudo_id = t.conteudo_id AND f.rotulo = t.falante_rotulo",
        (conteudo_id,),
    )


def ignored_speakers(conn: psycopg.Connection, conteudo_id: UUID) -> set[str]:
    rows = conn.execute(
        "SELECT rotulo FROM falante_conteudo WHERE conteudo_id = %s AND ignorado", (conteudo_id,)
    )
    return {row["rotulo"] for row in rows}


def replace_trechos(conn: psycopg.Connection, conteudo_id: UUID, chunks: list[Chunk]) -> None:
    conn.execute("DELETE FROM trecho WHERE conteudo_id = %s", (conteudo_id,))
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO trecho (conteudo_id, texto, inicio_s, fim_s, falante_rotulo) VALUES (%s, %s, %s, %s, %s)",
            [(conteudo_id, c.text, int(c.start), int(round(c.end)), c.speaker) for c in chunks],
        )
    sync_trecho_pessoas(conn, conteudo_id)


def trechos_to_embed(conn: psycopg.Connection, conteudo_id: UUID) -> list[tuple[UUID, str]]:
    rows = conn.execute("SELECT id, texto FROM trecho WHERE conteudo_id = %s ORDER BY inicio_s", (conteudo_id,))
    return [(row["id"], row["texto"]) for row in rows]


def save_embeddings(
    conn: psycopg.Connection, embeddings: list[tuple[UUID, list[float]]], model_name: str
) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE trecho SET embedding = %s::vector, modelo_embedding = %s WHERE id = %s",
            [(str(vector), model_name, trecho_id) for trecho_id, vector in embeddings],
        )


def _parse_vector(text: str) -> list[float]:
    return [float(value) for value in text.strip("[]").split(",")]
