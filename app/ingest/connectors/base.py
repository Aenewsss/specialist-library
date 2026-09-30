from pathlib import Path
from typing import Protocol

from app.ingest.models import ContentMetadata


class Connector(Protocol):
    """Um conector por fonte.tipo: sabe buscar metadados e mídia de um conteúdo."""

    def fetch_metadata(self, external_id: str) -> ContentMetadata: ...

    def download_audio(self, external_id: str, target_dir: Path) -> Path: ...
