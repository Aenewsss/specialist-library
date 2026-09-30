from app.ingest.chunk import ChunkingRules, chunk_segments
from app.ingest.models import Segment

RULES = ChunkingRules(min_duration_s=45, max_duration_s=60, overlap_s=10)


def continuous_speech(speaker: str, start: float, seconds: int, step: float = 2.5) -> list[Segment]:
    count = int(seconds / step)
    return [
        Segment(start=start + i * step, end=start + (i + 1) * step, text=f"{speaker}-{i}", speaker=speaker)
        for i in range(count)
    ]


def test_chunks_stay_within_duration_bounds_except_the_last():
    chunks = chunk_segments(continuous_speech("A", 0, 300), RULES)

    for chunk in chunks[:-1]:
        assert RULES.min_duration_s <= chunk.end - chunk.start <= RULES.max_duration_s
    assert chunks[-1].end == 300


def test_consecutive_chunks_overlap_by_about_the_configured_amount():
    chunks = chunk_segments(continuous_speech("A", 0, 300), RULES)

    for previous, current in zip(chunks, chunks[1:]):
        overlap = previous.end - current.start
        assert 0 < overlap <= RULES.overlap_s


def test_every_segment_is_covered():
    segments = continuous_speech("A", 0, 300)
    chunks = chunk_segments(segments, RULES)

    covered = " ".join(chunk.text for chunk in chunks).split()
    assert set(covered) == {segment.text for segment in segments}


def test_never_mixes_speakers_in_one_chunk():
    segments = continuous_speech("A", 0, 70) + continuous_speech("B", 70, 20) + continuous_speech("A", 90, 50)

    chunks = chunk_segments(segments, RULES)

    for chunk in chunks:
        assert {token.split("-")[0] for token in chunk.text.split()} == {chunk.speaker}
    assert [chunk.speaker for chunk in chunks] == ["A", "A", "B", "A"]


def test_short_turn_becomes_a_single_chunk():
    chunks = chunk_segments(continuous_speech("B", 0, 10), RULES)

    assert len(chunks) == 1 and chunks[0].end - chunks[0].start == 10


def test_prefers_cutting_at_the_longest_pause_inside_the_window():
    segments = continuous_speech("A", 0, 50)
    pause_at = 50 + 3  # pausa de 3 s depois do segmento que termina em 50 s
    segments += continuous_speech("A", pause_at, 60)

    first_chunk = chunk_segments(segments, RULES)[0]

    assert first_chunk.end == 50


def test_prefers_sentence_end_when_pauses_are_equal():
    segments = continuous_speech("A", 0, 100)
    segments[20] = Segment(start=50, end=52.5, text="fim da frase.", speaker="A")

    first_chunk = chunk_segments(segments, RULES)[0]

    assert first_chunk.end == 52.5


BRIDGING = ChunkingRules(min_duration_s=45, max_duration_s=60, overlap_s=10, max_interruption_s=3)


def test_short_interjection_does_not_split_the_speakers_chunk():
    segments = (
        continuous_speech("A", 0, 20)
        + [Segment(20, 21.5, "B-aparte", speaker="B")]
        + continuous_speech("A", 21.5, 20)
    )

    chunks = chunk_segments(segments, BRIDGING)

    a_chunks = [chunk for chunk in chunks if chunk.speaker == "A"]
    assert len(a_chunks) == 1 and "B-aparte" not in a_chunks[0].text
    assert [chunk.text for chunk in chunks if chunk.speaker == "B"] == ["B-aparte"]


def test_long_interruption_still_ends_the_chunk():
    segments = continuous_speech("A", 0, 20) + continuous_speech("B", 20, 10) + continuous_speech("A", 30, 20)

    chunks = chunk_segments(segments, BRIDGING)

    assert [chunk.speaker for chunk in chunks] == ["A", "B", "A"]


def test_bridging_is_off_by_default():
    segments = continuous_speech("A", 0, 20) + [Segment(20, 21, "B-aparte", speaker="B")] + continuous_speech("A", 21, 20)

    assert [chunk.speaker for chunk in chunk_segments(segments, RULES)] == ["A", "B", "A"]


def test_every_segment_lands_in_exactly_one_speakers_chunks():
    segments = (
        continuous_speech("A", 0, 30)
        + [Segment(30, 31, "B-x", speaker="B"), Segment(31, 32, "C-y", speaker="C")]
        + continuous_speech("A", 32, 30)
    )

    chunks = chunk_segments(segments, BRIDGING)

    for chunk in chunks:
        assert {token.split("-")[0] for token in chunk.text.split()} == {chunk.speaker}
    assert {token for chunk in chunks for token in chunk.text.split()} == {s.text for s in segments}
