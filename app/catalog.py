"""Cadastro de pessoas e conteúdos (repositório sobre o Postgres)."""
from dataclasses import dataclass
from uuid import UUID

import psycopg

from app.ingest.connectors.youtube import canonical_video_url, extract_video_id
from app.ingest.models import PIPELINE_STAGES


class PessoaNotFound(LookupError):
    pass


@dataclass(frozen=True)
class RegisteredVideo:
    conteudo_id: UUID
    video_id: str
    created: bool


def add_pessoa(conn: psycopg.Connection, nome: str, bio_curta: str | None = None) -> UUID:
    row = conn.execute(
        "INSERT INTO pessoa (nome, bio_curta) VALUES (%s, %s) RETURNING id", (nome, bio_curta)
    ).fetchone()
    conn.commit()
    return row["id"]


def add_youtube_video(conn: psycopg.Connection, url: str, dono_pessoa_id: UUID | None = None) -> RegisteredVideo:
    """Registra o vídeo e enfileira as etapas do pipeline. Idempotente por video_id
    (e completa etapas que faltarem, caso o pipeline tenha ganhado etapas novas)."""
    video_id = extract_video_id(url)
    with conn.transaction():
        if dono_pessoa_id is not None:
            _ensure_pessoa_exists(conn, dono_pessoa_id)
        fonte_id = _upsert_video_fonte(conn, video_id, dono_pessoa_id)
        conteudo_id, created = _upsert_conteudo(conn, fonte_id, video_id)
        _enqueue_pipeline(conn, conteudo_id)
    conn.commit()
    return RegisteredVideo(conteudo_id=conteudo_id, video_id=video_id, created=created)


def _ensure_pessoa_exists(conn: psycopg.Connection, pessoa_id: UUID) -> None:
    if conn.execute("SELECT 1 FROM pessoa WHERE id = %s", (pessoa_id,)).fetchone() is None:
        raise PessoaNotFound(f"Pessoa {pessoa_id} não cadastrada")


def _upsert_video_fonte(conn: psycopg.Connection, video_id: str, dono_pessoa_id: UUID | None) -> UUID:
    # No MVP a fonte é o próprio vídeo; na coleta por canal, a fonte vira o canal.
    # Quem fala em cada trecho vem da diarização, não do dono.
    return conn.execute(
        "INSERT INTO fonte (tipo, url, dono_pessoa_id) VALUES ('youtube', %s, %s)"
        " ON CONFLICT (tipo, url) DO UPDATE SET url = EXCLUDED.url RETURNING id",
        (canonical_video_url(video_id), dono_pessoa_id),
    ).fetchone()["id"]


def _upsert_conteudo(conn: psycopg.Connection, fonte_id: UUID, video_id: str) -> tuple[UUID, bool]:
    row = conn.execute(
        "INSERT INTO conteudo (fonte_id, id_externo, url_original) VALUES (%s, %s, %s)"
        " ON CONFLICT (fonte_id, id_externo) DO UPDATE SET url_original = EXCLUDED.url_original"
        " RETURNING id, (xmax = 0) AS created",
        (fonte_id, video_id, canonical_video_url(video_id)),
    ).fetchone()
    return row["id"], row["created"]


def _enqueue_pipeline(conn: psycopg.Connection, conteudo_id: UUID) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO job_ingestao (conteudo_id, etapa) VALUES (%s, %s)"
            " ON CONFLICT (conteudo_id, etapa) DO NOTHING",
            [(conteudo_id, etapa) for etapa in PIPELINE_STAGES],
        )
