"""Visão dos vídeos da biblioteca para a interface: andamento da ingestão e resultado."""
from collections.abc import Sequence
from dataclasses import dataclass

import psycopg

from app.ingest.models import PIPELINE_STAGES
from app.ingest.worker import MAX_ATTEMPTS

STAGE_LABELS = {
    "coleta": "Buscando dados do vídeo",
    "transcricao": "Transcrevendo",
    "diarizacao": "Separando as vozes",
    "atribuicao": "Reconhecendo quem fala",
    "chunking": "Dividindo em trechos",
    "embeddings": "Indexando para a busca",
}


@dataclass(frozen=True)
class JobState:
    etapa: str
    status: str
    tentativas: int
    erro: str | None


@dataclass(frozen=True)
class PipelineProgress:
    status: str  # na_fila | processando | pronto | erro
    current_stage: str | None
    stages_done: int
    error: str | None


def summarize_progress(jobs: Sequence[JobState]) -> PipelineProgress:
    """Resume os jobs de um conteúdo. Erro só conta como definitivo depois das retentativas."""
    ordered = sorted(jobs, key=lambda job: PIPELINE_STAGES.index(job.etapa))
    done = sum(job.status == "ok" for job in ordered)
    pending = [job for job in ordered if job.status != "ok"]
    if not pending:
        return PipelineProgress("pronto", None, done, None)
    current = pending[0]
    if current.status == "erro" and current.tentativas >= MAX_ATTEMPTS:
        return PipelineProgress("erro", current.etapa, done, current.erro)
    started = done > 0 or current.status in ("rodando", "erro")
    return PipelineProgress("processando" if started else "na_fila", current.etapa, done, None)


VIDEOS = """
SELECT c.id, c.id_externo, c.titulo, c.publicado_em, c.url_original, f.tipo AS fonte_tipo,
  (SELECT count(*) FROM trecho t WHERE t.conteudo_id = c.id) AS trechos,
  ARRAY(SELECT DISTINCT p.nome FROM trecho t JOIN pessoa p ON p.id = t.pessoa_id
        WHERE t.conteudo_id = c.id ORDER BY p.nome) AS pessoas,
  (SELECT count(*) FROM falante_conteudo fa
   WHERE fa.conteudo_id = c.id AND fa.pessoa_id IS NULL AND NOT fa.confirmado AND NOT fa.ignorado
     AND EXISTS (SELECT 1 FROM trecho t WHERE t.conteudo_id = c.id AND t.falante_rotulo = fa.rotulo)
  ) AS vozes_pendentes,
  (SELECT min(j.atualizado_em) FROM job_ingestao j WHERE j.conteudo_id = c.id) AS adicionado_em
FROM conteudo c JOIN fonte f ON f.id = c.fonte_id
ORDER BY adicionado_em DESC NULLS LAST
"""


def list_videos(conn: psycopg.Connection) -> list[dict]:
    rows = conn.execute(VIDEOS).fetchall()
    jobs = _jobs_by_conteudo(conn)
    return [_video(row, summarize_progress(jobs.get(row["id"], []))) for row in rows]


def _jobs_by_conteudo(conn: psycopg.Connection) -> dict:
    grouped: dict = {}
    for row in conn.execute("SELECT conteudo_id, etapa, status, tentativas, erro FROM job_ingestao"):
        grouped.setdefault(row["conteudo_id"], []).append(
            JobState(row["etapa"], row["status"], row["tentativas"], row["erro"])
        )
    return grouped


def _video(row: dict, progress: PipelineProgress) -> dict:
    return {
        "conteudo_id": str(row["id"]),
        "video_id": row["id_externo"],
        "titulo": row["titulo"],
        "publicado_em": row["publicado_em"].isoformat() if row["publicado_em"] else None,
        "url": row["url_original"],
        "status": progress.status,
        "etapa_atual": progress.current_stage,
        "etapa_atual_descricao": STAGE_LABELS.get(progress.current_stage) if progress.current_stage else None,
        "etapas_concluidas": progress.stages_done,
        "total_etapas": len(PIPELINE_STAGES),
        "erro": progress.error,
        "trechos": row["trechos"],
        "pessoas": row["pessoas"],
        "vozes_pendentes": row["vozes_pendentes"],
    }
