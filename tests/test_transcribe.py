from app.ingest.models import Segment
from app.ingest.transcribe import TimedWord, group_words, trim_rolling_overlaps


def test_rolling_caption_lines_are_trimmed_at_the_next_start():
    lines = [Segment(0.0, 4.0, "a"), Segment(1.8, 6.8, "b"), Segment(4.0, 9.3, "c")]

    trimmed = trim_rolling_overlaps(lines)

    assert [(s.start, s.end) for s in trimmed] == [(0.0, 1.8), (1.8, 4.0), (4.0, 9.3)]


def words(*items):
    return [TimedWord(start, end, text) for start, end, text in items]


def test_words_are_grouped_until_a_sentence_ends():
    pieces = group_words(words((0, 0.4, " o"), (0.4, 1.0, " dilúvio."), (1.0, 1.5, " Então")))

    assert [p.text for p in pieces] == ["o dilúvio.", "Então"]


def test_long_speech_is_split_into_short_pieces():
    long_run = words(*[(i * 0.5, i * 0.5 + 0.5, f" p{i}") for i in range(20)])  # 10 s sem pausa

    pieces = group_words(long_run, max_piece_s=3.0)

    assert all(p.end - p.start <= 3.0 for p in pieces)
    assert " ".join(p.text for p in pieces).split() == [f"p{i}" for i in range(20)]


def test_a_pause_closes_the_piece():
    pieces = group_words(words((0, 0.5, " sim"), (1.5, 2.0, " mas")))

    assert [p.text for p in pieces] == ["sim", "mas"]
