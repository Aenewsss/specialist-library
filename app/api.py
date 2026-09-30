from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import catalog, speakers
from app.config import get_config
from app.db import connect
from app.ingest.attribution import attribution_rules
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Modelos carregados e aquecidos uma vez por processo, antes de aceitar requisições.
    search = build_search_service(get_config())
    search.warm_up()
    app.state.search = search
    yield


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
