from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.config import get_config
from app.db import connect
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


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    with connect() as conn:
        return app.state.search.ask(conn, request.pergunta, request.to_filters())
