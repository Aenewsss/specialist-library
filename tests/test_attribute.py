from uuid import uuid4

from app.ingest.attribute import assign_speakers, match_voice
from app.ingest.models import Segment, SpeakerTurn


def test_segment_gets_the_speaker_with_most_overlap():
    turns = [SpeakerTurn(0, 1.0, "A"), SpeakerTurn(1.0, 4.0, "B")]

    [segment] = assign_speakers([Segment(0, 3, "texto")], turns)

    assert segment.speaker == "B"


def test_segment_without_any_turn_has_no_speaker():
    [segment] = assign_speakers([Segment(10, 12, "texto")], [SpeakerTurn(0, 5, "A")])

    assert segment.speaker is None


def test_voice_is_attributed_to_the_most_similar_person_above_threshold():
    sergio, rodrigo = uuid4(), uuid4()
    samples = {sergio: [[1.0, 0.0]], rodrigo: [[0.0, 1.0]]}

    match = match_voice([0.9, 0.1], samples, threshold=0.6)

    assert match.pessoa_id == sergio and match.similarity > 0.9


def test_voice_below_threshold_stays_unattributed():
    samples = {uuid4(): [[1.0, 0.0]]}

    match = match_voice([0.5, 0.5], samples, threshold=0.8)

    assert match.pessoa_id is None and match.similarity is not None


def test_no_samples_means_no_attribution():
    assert match_voice([1.0, 0.0], {}, threshold=0.6).pessoa_id is None
