"""Fila de ingestão sobre a própria tabela job_ingestao (FOR UPDATE SKIP LOCKED).

Uma etapa só roda quando todas as anteriores do mesmo conteúdo estão 'ok'.
Etapas pesadas rodam em sequência para não disputar memória da GPU.
"""
import logging
from dataclasses import dataclass, field
from uuid import UUID

import psycopg

from app.ingest.models import PIPELINE_STAGES
from app.ingest.stages import IngestionStages

MAX_ATTEMPTS = 3
STALE_RUNNING_AFTER = "1 hour"  # 'rodando' há mais que isso = worker morreu no meio

logger = logging.getLogger(__name__)

CLAIM_NEXT_JOB = f"""
WITH next_job AS (
  SELECT j.id FROM job_ingestao j
  WHERE (
      j.status = 'pendente'
      OR (j.status = 'erro' AND j.tentativas < %(max_attempts)s)
      OR (j.status = 'rodando' AND j.atualizado_em < now() - interval '{STALE_RUNNING_AFTER}')
    )
    AND NOT EXISTS (
      SELECT 1 FROM job_ingestao previous
      WHERE previous.conteudo_id = j.conteudo_id
        AND previous.status <> 'ok'
        AND array_position(%(stages)s::text[], previous.etapa) < array_position(%(stages)s::text[], j.etapa)
    )
  ORDER BY array_position(%(stages)s::text[], j.etapa), j.atualizado_em
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
UPDATE job_ingestao j
SET status = 'rodando', tentativas = j.tentativas + 1, erro = NULL, atualizado_em = now()
FROM next_job WHERE j.id = next_job.id
RETURNING j.id, j.conteudo_id, j.etapa, j.tentativas
"""


@dataclass(frozen=True)
class ClaimedJob:
    id: UUID
    conteudo_id: UUID
    etapa: str
    tentativas: int


@dataclass
class WorkerReport:
    succeeded: list[ClaimedJob] = field(default_factory=list)
    failed: list[tuple[ClaimedJob, str]] = field(default_factory=list)


def claim_next_job(conn: psycopg.Connection) -> ClaimedJob | None:
    with conn.transaction():
        row = conn.execute(
            CLAIM_NEXT_JOB, {"max_attempts": MAX_ATTEMPTS, "stages": list(PIPELINE_STAGES)}
        ).fetchone()
    return ClaimedJob(**row) if row else None


def finish_job(conn: psycopg.Connection, job: ClaimedJob, error: str | None = None) -> None:
    conn.execute(
        "UPDATE job_ingestao SET status = %s, erro = %s, atualizado_em = now() WHERE id = %s",
        ("erro" if error else "ok", error, job.id),
    )


def run_until_empty(conn: psycopg.Connection, stages: IngestionStages) -> WorkerReport:
    """Processa jobs até não haver mais nada executável. Exige conexão em autocommit."""
    report = WorkerReport()
    while (job := claim_next_job(conn)) is not None:
        logger.info("%s → %s (tentativa %d)", job.conteudo_id, job.etapa, job.tentativas)
        try:
            stages.handler_for(job.etapa)(job.conteudo_id)
        except Exception as error:  # qualquer falha de etapa vira retry, não derruba o worker
            logger.exception("Falhou: %s", job.etapa)
            finish_job(conn, job, error=f"{type(error).__name__}: {error}")
            report.failed.append((job, str(error)))
            continue
        finish_job(conn, job)
        report.succeeded.append(job)
    return report


def restart_from(conn: psycopg.Connection, conteudo_id: UUID, etapa: str) -> None:
    """Volta a etapa e as seguintes para 'pendente' (ex.: re-fatiar após mudar config)."""
    restart_only(conn, conteudo_id, list(PIPELINE_STAGES[PIPELINE_STAGES.index(etapa):]))


def restart_only(conn: psycopg.Connection, conteudo_id: UUID, etapas: list[str]) -> None:
    """Volta só as etapas indicadas. Útil porque transcrição e diarização são independentes:
    trocar a transcrição não precisa refazer a diarização (e perder os falantes confirmados)."""
    conn.execute(
        "UPDATE job_ingestao SET status = 'pendente', tentativas = 0, erro = NULL, atualizado_em = now()"
        " WHERE conteudo_id = %s AND etapa = ANY(%s)",
        (conteudo_id, etapas),
    )
