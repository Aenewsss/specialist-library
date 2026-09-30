from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import catalog, speakers, videos
from app.config import get_config
from app.db import connect
from app.ingest.attribution import attribution_rules
from app.ingest.background import BackgroundIngestor
from app.ingest.connectors.youtube import InvalidYoutubeUrl
from app.ingest.models import PIPELINE_STAGES
from app.ingest.worker import restart_from
from app.search.models import SearchFilters
from app.search.service import build_search_service


class AskRequest(BaseModel):
    pergunta: str = Field(min_length=3)
    pessoa_ids: list[UUID] = []
    area: str | None = None
    publicado_desde: date | None = None
    publicado_ate: date | None = None
    tipos_fonte: list[str] = []

    def to_filters(self) -> SearchFilters:
        return SearchFilters(
            pessoa_ids=self.pessoa_ids,
            area=self.area,
            published_from=self.publicado_desde,
            published_until=self.publicado_ate,
            fonte_tipos=self.tipos_fonte,
        )


class NewPessoaRequest(BaseModel):
    nome: str = Field(min_length=2)
    bio_curta: str | None = None


class ConfirmSpeakerRequest(BaseModel):
    pessoa_id: UUID


class AddVideoRequest(BaseModel):
    url: str = Field(min_length=10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Modelos carregados e aquecidos uma vez por processo, antes de aceitar requisições.
    config = get_config()
    search = build_search_service(config)
    search.warm_up()
    app.state.search = search
    app.state.ingestor = BackgroundIngestor(config)
    app.state.ingestor.start()
    yield
    app.state.ingestor.stop()


app = FastAPI(title="Biblioteca de Especialistas", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/pessoas")
def pessoas(todas: bool = False) -> list[dict]:
    """Por padrão, só quem tem trechos (o filtro da busca); com todas=true, todo o cadastro."""
    with connect() as conn:
        return catalog.list_all_pessoas(conn) if todas else catalog.list_pessoas_with_trechos(conn)


@app.post("/pessoas", status_code=201)
def create_pessoa(request: NewPessoaRequest) -> dict:
    with connect() as conn:
        pessoa_id = catalog.add_pessoa(conn, request.nome.strip(), request.bio_curta)
    return {"id": str(pessoa_id), "nome": request.nome.strip(), "bio_curta": request.bio_curta}


@app.get("/falantes/pendentes")
def pending_speakers() -> list[dict]:
    with connect() as conn:
        return speakers.list_pending_speakers(conn)


@app.post("/falantes/{conteudo_id}/{rotulo}/confirmar")
def confirm_speaker(conteudo_id: UUID, rotulo: str, request: ConfirmSpeakerRequest) -> dict:
    try:
        with connect() as conn:
            propagated = speakers.confirm_and_propagate(
                conn, conteudo_id, rotulo, request.pessoa_id, attribution_rules(get_config())
            )
    except (speakers.SpeakerNotFound, catalog.PessoaNotFound) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"confirmado": True, "outras_vozes_reconhecidas": propagated}


@app.post("/falantes/{conteudo_id}/{rotulo}/ignorar")
def ignore_speaker(conteudo_id: UUID, rotulo: str) -> dict:
    try:
        with connect() as conn:
            removed = speakers.ignore_speaker(conn, conteudo_id, rotulo)
    except speakers.SpeakerNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"ignorado": True, "trechos_removidos": removed}


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    with connect() as conn:
        return app.state.search.ask(conn, request.pergunta, request.to_filters())


@app.get("/videos")
def list_videos() -> list[dict]:
    with connect() as conn:
        return videos.list_videos(conn)


@app.post("/videos", status_code=201)
def add_video(request: AddVideoRequest) -> dict:
    try:
        with connect() as conn:
            registered = catalog.add_youtube_video(conn, request.url)
    except InvalidYoutubeUrl as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    app.state.ingestor.trigger()
    return {"conteudo_id": str(registered.conteudo_id), "video_id": registered.video_id, "novo": registered.created}


@app.post("/videos/{conteudo_id}/tentar-de-novo")
def retry_video(conteudo_id: UUID) -> dict:
    """Recomeça da etapa que falhou (as anteriores já estão prontas)."""
    with connect() as conn:
        failed = conn.execute(
            "SELECT etapa FROM job_ingestao WHERE conteudo_id = %s AND status = 'erro'", (conteudo_id,)
        ).fetchall()
        if not failed:
            raise HTTPException(status_code=404, detail="Nenhuma etapa com erro nesse vídeo")
        first_failed = min((row["etapa"] for row in failed), key=PIPELINE_STAGES.index)
        restart_from(conn, conteudo_id, first_failed)
        conn.commit()
    app.state.ingestor.trigger()
    return {"reiniciado_em": first_failed}
