from app.ingest.models import PIPELINE_STAGES
from app.ingest.worker import MAX_ATTEMPTS
from app.videos import JobState, summarize_progress


def jobs(**status_by_stage):
    return [
        JobState(stage, status_by_stage.get(stage, "pendente"), 1 if stage in status_by_stage else 0, None)
        for stage in PIPELINE_STAGES
    ]


def test_nothing_started_is_queued():
    progress = summarize_progress(jobs())

    assert (progress.status, progress.current_stage, progress.stages_done) == ("na_fila", "coleta", 0)


def test_running_stage_is_reported():
    progress = summarize_progress(jobs(coleta="ok", transcricao="ok", diarizacao="rodando"))

    assert (progress.status, progress.current_stage, progress.stages_done) == ("processando", "diarizacao", 2)


def test_all_ok_is_ready():
    progress = summarize_progress(jobs(**{stage: "ok" for stage in PIPELINE_STAGES}))

    assert (progress.status, progress.stages_done) == ("pronto", len(PIPELINE_STAGES))


def test_error_with_retries_left_is_still_processing():
    progress = summarize_progress(jobs(coleta="erro"))

    assert progress.status == "processando"


def test_error_after_all_attempts_is_final():
    states = jobs(coleta="ok")
    states[1] = JobState("transcricao", "erro", MAX_ATTEMPTS, "TranscriptUnavailable: sem legenda")

    progress = summarize_progress(states)

    assert (progress.status, progress.current_stage, progress.error) == (
        "erro", "transcricao", "TranscriptUnavailable: sem legenda",
    )
