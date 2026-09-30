import pytest

from app import catalog
from app.db import connect
from app.ingest.models import PIPELINE_STAGES
from app.ingest.worker import MAX_ATTEMPTS, restart_from, run_until_empty

pytestmark = pytest.mark.db


class RecordingStages:
    def __init__(self, failing: dict[str, int] | None = None):
        self.calls: list[str] = []
        self._remaining_failures = dict(failing or {})

    def handler_for(self, etapa):
        def handler(conteudo_id):
            self.calls.append(etapa)
            if self._remaining_failures.get(etapa, 0) > 0:
                self._remaining_failures[etapa] -= 1
                raise RuntimeError(f"{etapa} quebrou")
        return handler


@pytest.fixture
def worker_conn(test_database_url, db):
    with connect(test_database_url, autocommit=True) as conn:
        yield conn


@pytest.fixture
def conteudo_id(db):
    return catalog.add_youtube_video(db, "https://youtu.be/qgikRaQkPGU").conteudo_id


def statuses(conn, conteudo_id):
    rows = conn.execute("SELECT etapa, status FROM job_ingestao WHERE conteudo_id = %s", (conteudo_id,))
    return {row["etapa"]: row["status"] for row in rows}


def test_runs_stages_in_pipeline_order(worker_conn, conteudo_id):
    stages = RecordingStages()

    report = run_until_empty(worker_conn, stages)

    assert stages.calls == list(PIPELINE_STAGES)
    assert len(report.succeeded) == len(PIPELINE_STAGES)
    assert set(statuses(worker_conn, conteudo_id).values()) == {"ok"}


def test_failed_stage_is_retried_and_later_stages_wait(worker_conn, conteudo_id):
    stages = RecordingStages(failing={"diarizacao": 1})

    run_until_empty(worker_conn, stages)

    assert stages.calls.count("diarizacao") == 2
    assert stages.calls.index("atribuicao") > stages.calls.index("diarizacao")


def test_stage_failing_every_attempt_blocks_the_rest(worker_conn, conteudo_id):
    stages = RecordingStages(failing={"diarizacao": MAX_ATTEMPTS})

    report = run_until_empty(worker_conn, stages)

    assert len(report.failed) == MAX_ATTEMPTS
    assert "atribuicao" not in stages.calls
    assert statuses(worker_conn, conteudo_id)["diarizacao"] == "erro"


def test_restart_from_reprocesses_only_that_stage_and_later(worker_conn, conteudo_id):
    run_until_empty(worker_conn, RecordingStages())

    restart_from(worker_conn, conteudo_id, "chunking")
    stages = RecordingStages()
    run_until_empty(worker_conn, stages)

    assert stages.calls == ["chunking", "embeddings"]


def test_restart_only_reprocesses_just_the_chosen_stages(worker_conn, conteudo_id):
    from app.ingest.worker import restart_only

    run_until_empty(worker_conn, RecordingStages())

    restart_only(worker_conn, conteudo_id, ["transcricao", "chunking", "embeddings"])
    stages = RecordingStages()
    run_until_empty(worker_conn, stages)

    assert stages.calls == ["transcricao", "chunking", "embeddings"]
