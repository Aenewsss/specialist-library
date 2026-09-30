import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Segredos (HF_TOKEN) ficam no .env; carregado aqui para valer no CLI, na API e nos scripts.
load_dotenv(PROJECT_ROOT / ".env")
CONFIG_PATH = Path(os.environ.get("BIBLIOTECA_CONFIG", PROJECT_ROOT / "config.yaml"))


class ModelosConfig(BaseModel):
    device: str = "auto"
    embedding: str
    reranker: str
    whisper: str
    diarizacao: str


class ChunkConfig(BaseModel):
    duracao_min_s: int
    duracao_max_s: int
    sobreposicao_s: int
    max_interrupcao_s: float = 0.0


class BuscaConfig(BaseModel):
    candidatos: int
    rrf_k: int
    top_reranker: int
    limiar_reranker: float
    limiar_relacionados: float | None = None
    max_relacionados: int = 3


class TranscricaoConfig(BaseModel):
    idiomas: list[str]
    preferir: Literal["legenda_youtube", "whisper"] = "legenda_youtube"


class AtribuicaoConfig(BaseModel):
    limiar_voz: float
    min_segundos_fala: float = 5.0


class ApiConfig(BaseModel):
    host: str
    port: int

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


class Config(BaseModel):
    database_url: str
    api: ApiConfig
    dados_dir: Path
    modelos: ModelosConfig
    transcricao: TranscricaoConfig
    atribuicao: AtribuicaoConfig
    chunk: ChunkConfig
    busca: BuscaConfig


def load_config(path: Path = CONFIG_PATH) -> Config:
    raw = yaml.safe_load(path.read_text())
    # DATABASE_URL no ambiente tem precedência, para testes e deploy.
    raw["database_url"] = os.environ.get("DATABASE_URL", raw["database_url"])
    raw["dados_dir"] = PROJECT_ROOT / raw["dados_dir"]
    return Config.model_validate(raw)


@lru_cache
def get_config() -> Config:
    return load_config()
