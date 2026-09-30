"""Ingestão em segundo plano dentro da API: quem adiciona um vídeo pela interface não
precisa rodar `biblioteca ingest`. Uma thread só, porque as etapas pesadas não devem
disputar memória da GPU; a fila continua sendo a tabela job_ingestao."""
import logging
import threading

from app.config import Config
from app.db import connect
from app.ingest.stages import IngestionStages, PipelineServices
from app.ingest.worker import run_until_empty

IDLE_POLL_S = 30  # também pega vídeos cadastrados pelo terminal

logger = logging.getLogger(__name__)


class BackgroundIngestor:
    def __init__(self, config: Config):
        self._config = config
        self._services = PipelineServices(config)  # modelos carregam só quando uma etapa precisa
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="ingestao", daemon=True)

    def start(self) -> None:
        self._thread.start()
        self.trigger()

    def trigger(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stopping.set()
        self._wake.set()
        self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stopping.is_set():
            self._wake.wait(timeout=IDLE_POLL_S)
            self._wake.clear()
            if not self._stopping.is_set():
                self._drain_queue()

    def _drain_queue(self) -> None:
        try:
            with connect(autocommit=True) as conn:
                report = run_until_empty(conn, IngestionStages(conn, self._services, self._config))
        except Exception:  # banco fora do ar etc.: tenta de novo no próximo ciclo
            logger.exception("Ingestão em segundo plano falhou")
            return
        if report.succeeded or report.failed:
            logger.info("Ingestão: %d etapas ok, %d com erro", len(report.succeeded), len(report.failed))
