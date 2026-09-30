"""Fatia a transcrição em trechos de busca: um falante por trecho, 45–60 s, com sobreposição.

Num debate, interjeições curtas ("é", "30 metros") picotariam a fala de quem está com a
palavra. A fala continua através dessas interrupções: o trecho junta só as frases de quem
fala, e as frases de quem interrompeu viram trechos à parte, atribuídos a quem as disse.

Legenda automática não tem pontuação, então "não cortar no meio da frase" vira
"cortar na maior pausa dentro da janela", com bônus para fim de frase pontuado.
"""
from collections.abc import Sequence
from dataclasses import dataclass

from app.ingest.models import Chunk, Segment

SENTENCE_ENDINGS = (".", "?", "!", "…")
SENTENCE_END_BONUS_S = 1.0  # peso de um ponto final, em "segundos de pausa" equivalentes


@dataclass(frozen=True)
class ChunkingRules:
    min_duration_s: float
    max_duration_s: float
    overlap_s: float
    max_interruption_s: float = 0.0


def chunk_segments(segments: Sequence[Segment], rules: ChunkingRules) -> list[Chunk]:
    ordered = sorted(segments, key=lambda segment: segment.start)
    chunks: list[Chunk] = []
    for run in speaker_runs(ordered, rules.max_interruption_s):
        chunks.extend(_chunk_single_speaker(run, rules))
    return sorted(chunks, key=lambda chunk: chunk.start)


def speaker_runs(ordered: Sequence[Segment], max_interruption_s: float) -> list[list[Segment]]:
    """Blocos contínuos de um mesmo falante. Uma interrupção de outros falantes que dura até
    `max_interruption_s` e depois devolve a palavra não encerra o bloco: vira bloco próprio."""
    runs: list[list[Segment]] = []
    index = 0
    while index < len(ordered):
        run, interruptions, index = _extend_run(ordered, index, max_interruption_s)
        runs.append(run)
        runs.extend(interruptions)
    return runs


def _extend_run(
    ordered: Sequence[Segment], first: int, max_interruption_s: float
) -> tuple[list[Segment], list[list[Segment]], int]:
    speaker = ordered[first].speaker
    run, interruptions, index = [ordered[first]], [], first + 1
    while index < len(ordered):
        if ordered[index].speaker == speaker:
            run.append(ordered[index])
            index += 1
            continue
        resume = _resume_index(ordered, index, speaker, max_interruption_s)
        if resume is None:
            break
        interruptions.extend(_group_consecutive_by_speaker(ordered[index:resume]))
        index = resume
    return run, interruptions, index


def _resume_index(
    ordered: Sequence[Segment], start: int, speaker: str | None, max_interruption_s: float
) -> int | None:
    """Índice onde `speaker` volta a falar, se a interrupção couber no limite."""
    for index in range(start, len(ordered)):
        if ordered[index].start - ordered[start].start > max_interruption_s:
            return None
        if ordered[index].speaker == speaker:
            return index
    return None


def _group_consecutive_by_speaker(segments: Sequence[Segment]) -> list[list[Segment]]:
    groups: list[list[Segment]] = []
    for segment in segments:
        if groups and groups[-1][-1].speaker == segment.speaker:
            groups[-1].append(segment)
        else:
            groups.append([segment])
    return groups


def _chunk_single_speaker(run: list[Segment], rules: ChunkingRules) -> list[Chunk]:
    chunks, first = [], 0
    while first < len(run):
        last = _choose_cut(run, first, rules)
        chunks.append(_build_chunk(run[first : last + 1]))
        if last == len(run) - 1:
            break
        first = _next_start_with_overlap(run, first, last, rules.overlap_s)
    return chunks


def _choose_cut(run: list[Segment], first: int, rules: ChunkingRules) -> int:
    """Índice do último segmento do trecho que começa em `first`."""
    window_start = run[first].start
    candidates = [
        index
        for index in range(first, len(run))
        if rules.min_duration_s <= run[index].end - window_start <= rules.max_duration_s
    ]
    if candidates:
        return max(candidates, key=lambda index: _cut_score(run, index))
    return _last_index_within(run, first, rules.max_duration_s)


def _last_index_within(run: list[Segment], first: int, max_duration_s: float) -> int:
    """Sem candidato na janela: o run acaba antes do mínimo, ou um segmento estoura o máximo."""
    last = first
    while last + 1 < len(run) and run[last + 1].end - run[first].start <= max_duration_s:
        last += 1
    return last


def _cut_score(run: list[Segment], index: int) -> float:
    pause_after = run[index + 1].start - run[index].end if index + 1 < len(run) else float("inf")
    sentence_bonus = SENTENCE_END_BONUS_S if run[index].text.rstrip().endswith(SENTENCE_ENDINGS) else 0.0
    return pause_after + sentence_bonus


def _next_start_with_overlap(run: list[Segment], first: int, last: int, overlap_s: float) -> int:
    """Primeiro segmento dentro dos últimos `overlap_s` do trecho; sempre avança."""
    overlap_from = run[last].end - overlap_s
    for index in range(first + 1, last + 1):
        if run[index].start >= overlap_from:
            return index
    return last + 1


def _build_chunk(segments: list[Segment]) -> Chunk:
    return Chunk(
        start=segments[0].start,
        end=segments[-1].end,
        text=" ".join(segment.text.strip() for segment in segments),
        speaker=segments[0].speaker,
    )
