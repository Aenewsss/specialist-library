from uuid import uuid4

import pytest

from app import catalog
from app.db import apply_migrations
from app.ingest.models import PIPELINE_STAGES

pytestmark = pytest.mark.db

VIDEO_URL = "https://www.youtube.com/watch?v=qgikRaQkPGU"


def test_migrations_are_idempotent(db):
    assert apply_migrations(db) == []


def test_add_video_registers_conteudo_and_enqueues_mvp_stages(db):
    pessoa_id = catalog.add_pessoa(db, "Fulano")

    registered = catalog.add_youtube_video(db, VIDEO_URL, pessoa_id)

    assert registered.created and registered.video_id == "qgikRaQkPGU"
    jobs = db.execute(
        "SELECT etapa, status FROM job_ingestao WHERE conteudo_id = %s", (registered.conteudo_id,)
    ).fetchall()
    assert {job["etapa"] for job in jobs} == set(PIPELINE_STAGES)
    assert {job["status"] for job in jobs} == {"pendente"}


def test_add_same_video_twice_does_not_duplicate(db):
    pessoa_id = catalog.add_pessoa(db, "Fulano")

    first = catalog.add_youtube_video(db, VIDEO_URL, pessoa_id)
    second = catalog.add_youtube_video(db, "https://youtu.be/qgikRaQkPGU", pessoa_id)

    assert second.conteudo_id == first.conteudo_id and not second.created
    assert db.execute("SELECT count(*) AS n FROM job_ingestao").fetchone()["n"] == len(PIPELINE_STAGES)


def test_add_video_for_unknown_pessoa_fails(db):
    with pytest.raises(catalog.PessoaNotFound):
        catalog.add_youtube_video(db, VIDEO_URL, uuid4())


def test_lists_only_people_who_have_trechos(db):
    from app.ingest import repository
    from app.ingest.models import Chunk

    speaker = catalog.add_pessoa(db, "Com trecho")
    catalog.add_pessoa(db, "Sem trecho")
    conteudo_id = catalog.add_youtube_video(db, VIDEO_URL).conteudo_id
    with db.transaction():
        repository.replace_trechos(db, conteudo_id, [Chunk(0, 10, "fala", "SPEAKER_00")])
        db.execute("UPDATE trecho SET pessoa_id = %s", (speaker,))

    assert [p["nome"] for p in catalog.list_pessoas_with_trechos(db)] == ["Com trecho"]
