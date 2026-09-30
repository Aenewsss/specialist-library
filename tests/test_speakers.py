import pytest

from app import catalog, speakers
from app.ingest import repository
from app.ingest.models import Chunk, Diarization, SpeakerTurn

pytestmark = pytest.mark.db

VOICE_A = [1.0] + [0.0] * 255
VOICE_B = [0.0, 1.0] + [0.0] * 254


@pytest.fixture
def diarized_video(db):
    conteudo_id = catalog.add_youtube_video(db, "https://youtu.be/qgikRaQkPGU").conteudo_id
    diarization = Diarization(
        turns=[SpeakerTurn(0, 30, "SPEAKER_00"), SpeakerTurn(30, 40, "SPEAKER_01")],
        voice_embeddings={"SPEAKER_00": VOICE_A, "SPEAKER_01": VOICE_B},
    )
    with db.transaction():
        repository.save_diarization(db, conteudo_id, diarization)
        repository.replace_trechos(
            db, conteudo_id, [Chunk(0, 30, "fala A", "SPEAKER_00"), Chunk(30, 40, "fala B", "SPEAKER_01")]
        )
    return conteudo_id


def test_confirming_a_speaker_attributes_its_trechos_and_stores_a_voice_sample(db, diarized_video):
    sergio = catalog.add_pessoa(db, "Sérgio Sacani")

    speakers.confirm_speaker(db, diarized_video, "SPEAKER_00", sergio)

    trechos = db.execute("SELECT texto, pessoa_id, revisado FROM trecho ORDER BY inicio_s").fetchall()
    assert (trechos[0]["pessoa_id"], trechos[0]["revisado"]) == (sergio, True)
    assert trechos[1]["pessoa_id"] is None
    assert repository.voice_samples_by_pessoa(db) == {sergio: [VOICE_A]}


def test_confirming_twice_does_not_duplicate_samples(db, diarized_video):
    sergio = catalog.add_pessoa(db, "Sérgio Sacani")

    speakers.confirm_speaker(db, diarized_video, "SPEAKER_00", sergio)
    speakers.confirm_speaker(db, diarized_video, "SPEAKER_00", sergio)

    assert db.execute("SELECT count(*) AS n FROM amostra_voz").fetchone()["n"] == 1


def test_listing_shows_speakers_by_talk_time_with_timestamped_links(db, diarized_video):
    summaries = speakers.list_speakers(db, diarized_video)

    assert [s.label for s in summaries] == ["SPEAKER_00", "SPEAKER_01"]
    assert summaries[0].sample_links == ["https://www.youtube.com/watch?v=qgikRaQkPGU&t=0s"]


def test_unknown_speaker_label_fails(db, diarized_video):
    with pytest.raises(speakers.SpeakerNotFound):
        speakers.confirm_speaker(db, diarized_video, "SPEAKER_09", catalog.add_pessoa(db, "X"))


def test_ignoring_a_speaker_removes_its_trechos(db, diarized_video):
    removed = speakers.ignore_speaker(db, diarized_video, "SPEAKER_01")

    assert removed == 1
    assert [row["falante_rotulo"] for row in db.execute("SELECT falante_rotulo FROM trecho")] == ["SPEAKER_00"]
    assert repository.ignored_speakers(db, diarized_video) == {"SPEAKER_01"}
    assert "SPEAKER_01" not in {s.label for s in repository.unconfirmed_speakers(db, diarized_video)}


def test_speaker_without_valid_voice_is_stored_without_embedding(db):
    conteudo_id = catalog.add_youtube_video(db, "https://youtu.be/0LS2F1PPH74").conteudo_id
    diarization = Diarization(turns=[SpeakerTurn(0, 30, "SPEAKER_00")], voice_embeddings={"SPEAKER_00": VOICE_A, "SPEAKER_01": None})
    with db.transaction():
        repository.save_diarization(db, conteudo_id, diarization)

    assert [s.label for s in repository.unconfirmed_speakers(db, conteudo_id)] == ["SPEAKER_00"]


def test_pending_lists_unattributed_voices_with_samples(db, diarized_video):
    [pending_a, pending_b] = sorted(speakers.list_pending_speakers(db), key=lambda p: p["rotulo"])

    assert (pending_a["rotulo"], pending_b["rotulo"]) == ("SPEAKER_00", "SPEAKER_01")
    assert pending_a["amostras"] == [
        {"inicio_s": 0, "texto": "fala A", "link": "https://www.youtube.com/watch?v=qgikRaQkPGU&t=0s"}
    ]


def test_confirmed_or_ignored_voices_leave_the_pending_list(db, diarized_video):
    speakers.confirm_speaker(db, diarized_video, "SPEAKER_00", catalog.add_pessoa(db, "Sérgio Sacani"))
    speakers.ignore_speaker(db, diarized_video, "SPEAKER_01")

    assert speakers.list_pending_speakers(db) == []


def test_confirming_a_voice_recognizes_the_same_voice_in_another_video(db, diarized_video):
    from app.ingest.attribution import AttributionRules

    other_video = catalog.add_youtube_video(db, "https://youtu.be/8ZlY48EJwSw").conteudo_id
    with db.transaction():
        repository.save_diarization(
            db, other_video,
            Diarization(turns=[SpeakerTurn(0, 60, "SPEAKER_07")], voice_embeddings={"SPEAKER_07": VOICE_A}),
        )
        repository.replace_trechos(db, other_video, [Chunk(0, 60, "outra fala A", "SPEAKER_07")])
    sergio = catalog.add_pessoa(db, "Sérgio Sacani")
    rules = AttributionRules(voice_threshold=0.6, min_speaking_seconds=5)

    recognized = speakers.confirm_and_propagate(db, diarized_video, "SPEAKER_00", sergio, rules)

    assert recognized == 1
    trecho = db.execute("SELECT pessoa_id, revisado FROM trecho WHERE conteudo_id = %s", (other_video,)).fetchone()
    assert (trecho["pessoa_id"], trecho["revisado"]) == (sergio, False)  # automático, não revisado


def test_confirming_with_unknown_pessoa_fails(db, diarized_video):
    from uuid import uuid4

    from app.ingest.attribution import AttributionRules

    with pytest.raises(catalog.PessoaNotFound):
        speakers.confirm_and_propagate(db, diarized_video, "SPEAKER_00", uuid4(), AttributionRules(0.6, 5))


def test_propagation_counts_only_voices_that_had_no_author(db, diarized_video):
    from app.ingest.attribution import AttributionRules, attribute_all_pending

    rules = AttributionRules(voice_threshold=0.6, min_speaking_seconds=5)
    speakers.confirm_speaker(db, diarized_video, "SPEAKER_00", catalog.add_pessoa(db, "Sérgio Sacani"))
    other_video = catalog.add_youtube_video(db, "https://youtu.be/8ZlY48EJwSw").conteudo_id
    with db.transaction():
        repository.save_diarization(
            db, other_video,
            Diarization(turns=[SpeakerTurn(0, 60, "SPEAKER_07")], voice_embeddings={"SPEAKER_07": VOICE_A}),
        )

    assert attribute_all_pending(db, rules) == 1
    assert attribute_all_pending(db, rules) == 0  # já tinha autor: não conta de novo
