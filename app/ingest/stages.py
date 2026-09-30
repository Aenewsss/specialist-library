"""Uma função por etapa do pipeline. Cada etapa lê do banco o que a anterior gravou
e sobrescreve só o próprio resultado, então rodar de novo não duplica nada."""
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from uuid import UUID

import psycopg

from app.config import Config
from app.ingest import repository
from app.ingest.attribute import assign_speakers
from app.ingest.attribution import attribute_conteudo, attribution_rules
from app.ingest.chunk import ChunkingRules, chunk_segments
from app.ingest.connectors.base import Connector
from app.ingest.connectors.youtube import YoutubeConnector
from app.ingest.devices import resolve_device
from app.ingest.diarize import Diarizer, PyannoteDiarizer
from app.ingest.embed import Embedder, SentenceTransformerEmbedder
from app.ingest.transcribe import Transcriber, WhisperTranscriber, YoutubeCaptionSource, transcribe_video


class UnsupportedSource(ValueError):
    pass


class PipelineServices:
    """Modelos pesados carregados sob demanda: uma etapa só paga pelo que usa."""

    def __init__(self, config: Config):
        self._config = config
        self._device = resolve_device(config.modelos.device)

    @cached_property
    def connectors(self) -> dict[str, Connector]:
        return {"youtube": YoutubeConnector()}

    @cached_property
    def captions(self) -> YoutubeCaptionSource:
        return YoutubeCaptionSource(self._config.transcricao.idiomas)

    @cached_property
    def transcriber(self) -> Transcriber:
        return WhisperTranscriber(self._config.modelos.whisper, language=self._config.transcricao.idiomas[0])

    @cached_property
    def diarizer(self) -> Diarizer:
        return PyannoteDiarizer(self._config.modelos.diarizacao, self._device)

    @cached_property
    def embedder(self) -> Embedder:
        return SentenceTransformerEmbedder(self._config.modelos.embedding, self._device)


@dataclass
class IngestionStages:
    conn: psycopg.Connection
    services: PipelineServices
    config: Config

    def handler_for(self, etapa: str) -> Callable[[UUID], None]:
        return {
            "coleta": self.collect,
            "transcricao": self.transcribe,
            "diarizacao": self.diarize,
            "atribuicao": self.attribute,
            "chunking": self.chunk,
            "embeddings": self.embed,
        }[etapa]

    def collect(self, conteudo_id: UUID) -> None:
        conteudo = repository.get_conteudo(self.conn, conteudo_id)
        metadata = self._connector(conteudo.fonte_tipo).fetch_metadata(conteudo.external_id)
        with self.conn.transaction():
            repository.save_metadata(self.conn, conteudo_id, metadata)

    def transcribe(self, conteudo_id: UUID) -> None:
        conteudo = repository.get_conteudo(self.conn, conteudo_id)
        transcript = transcribe_video(
            conteudo.external_id,
            self.services.captions,
            self.services.transcriber,
            get_audio=lambda: self._audio_path(conteudo),
            prefer=self.config.transcricao.preferir,
        )
        with self.conn.transaction():
            repository.save_transcript(self.conn, conteudo_id, transcript.segments, transcript.origin)

    def diarize(self, conteudo_id: UUID) -> None:
        conteudo = repository.get_conteudo(self.conn, conteudo_id)
        diarization = self.services.diarizer.diarize(self._audio_path(conteudo))
        with self.conn.transaction():
            repository.save_diarization(self.conn, conteudo_id, diarization)

    def attribute(self, conteudo_id: UUID) -> None:
        attribute_conteudo(self.conn, conteudo_id, attribution_rules(self.config))

    def chunk(self, conteudo_id: UUID) -> None:
        conteudo = repository.get_conteudo(self.conn, conteudo_id)
        ignored = repository.ignored_speakers(self.conn, conteudo_id)
        segments = [
            segment
            for segment in assign_speakers(conteudo.segments, conteudo.turns)
            if segment.speaker not in ignored
        ]
        rules = ChunkingRules(
            min_duration_s=self.config.chunk.duracao_min_s,
            max_duration_s=self.config.chunk.duracao_max_s,
            overlap_s=self.config.chunk.sobreposicao_s,
            max_interruption_s=self.config.chunk.max_interrupcao_s,
        )
        with self.conn.transaction():
            repository.replace_trechos(self.conn, conteudo_id, chunk_segments(segments, rules))

    def embed(self, conteudo_id: UUID) -> None:
        trechos = repository.trechos_to_embed(self.conn, conteudo_id)
        vectors = self.services.embedder.embed([texto for _, texto in trechos])
        with self.conn.transaction():
            repository.save_embeddings(
                self.conn, [(trecho_id, vector) for (trecho_id, _), vector in zip(trechos, vectors)],
                self.services.embedder.model_name,
            )

    def _connector(self, fonte_tipo: str) -> Connector:
        try:
            return self.services.connectors[fonte_tipo]
        except KeyError:
            raise UnsupportedSource(f"Sem conector para fonte do tipo '{fonte_tipo}'") from None

    def _audio_path(self, conteudo: repository.ConteudoRecord):
        connector = self._connector(conteudo.fonte_tipo)
        return connector.download_audio(conteudo.external_id, self.config.dados_dir / "audio")
