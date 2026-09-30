"""Métricas da avaliação. Funções puras sobre candidatos já pontuados: a busca e o reranking
rodam uma vez por pergunta, e a varredura de limiar só refiltra esses resultados."""
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.search.models import ScoredCandidate

RECALL_AT = 5


@dataclass(frozen=True)
class TestQuestion:
    __test__ = False  # o nome começa com "Test"; impede o pytest de coletar a classe

    question: str
    video_id: str | None = None
    pessoa: str | None = None
    intervals: tuple[tuple[int, int], ...] = ()
    unanswerable: bool = False


def load_questions(path: Path) -> list[TestQuestion]:
    return [_parse_question(raw) for raw in yaml.safe_load(path.read_text())]


def _parse_question(raw: dict) -> TestQuestion:
    intervals = raw.get("resposta_entre_s") or []
    if intervals and not isinstance(intervals[0], list):
        intervals = [intervals]
    return TestQuestion(
        question=raw["pergunta"],
        video_id=raw.get("video_id"),
        pessoa=raw.get("pessoa"),
        intervals=tuple((start, end) for start, end in intervals),
        unanswerable=bool(raw.get("sem_resposta")),
    )


def is_hit(item: ScoredCandidate, question: TestQuestion) -> bool:
    """Acerto: mesmo vídeo, intervalo sobreposto ao esperado e, se indicada, a pessoa certa."""
    candidate = item.candidate
    if question.video_id and candidate.external_id != question.video_id:
        return False
    if question.pessoa and candidate.pessoa_nome != question.pessoa:
        return False
    return any(candidate.inicio_s < end and candidate.fim_s > start for start, end in question.intervals)


@dataclass(frozen=True)
class QuestionRun:
    question: TestQuestion
    ranked: list[ScoredCandidate]  # ordenado por nota, maior primeiro

    def kept(self, threshold: float, max_results: int) -> list[ScoredCandidate]:
        return [item for item in self.ranked if item.score >= threshold][:max_results]

    def first_hit_rank(self, threshold: float, max_results: int) -> int | None:
        for rank, item in enumerate(self.kept(threshold, max_results), start=1):
            if is_hit(item, self.question):
                return rank
        return None


@dataclass(frozen=True)
class Metrics:
    threshold: float
    recall_at_5: float
    mrr: float
    not_found_precision: float  # sem resposta → vazio
    false_empty_rate: float  # com resposta → vazio por causa do limiar

    def balance(self) -> float:
        """O limiar bom equilibra as duas taxas: o pior dos dois lados é o que importa."""
        return min(self.not_found_precision, 1 - self.false_empty_rate)


def evaluate(runs: Sequence[QuestionRun], threshold: float, max_results: int) -> Metrics:
    answerable = [run for run in runs if not run.question.unanswerable]
    unanswerable = [run for run in runs if run.question.unanswerable]
    ranks = [run.first_hit_rank(threshold, max_results) for run in answerable]
    return Metrics(
        threshold=threshold,
        recall_at_5=_share(answerable, [rank is not None and rank <= RECALL_AT for rank in ranks]),
        mrr=_mean([1 / rank if rank else 0.0 for rank in ranks]),
        not_found_precision=_share(unanswerable, [not run.kept(threshold, max_results) for run in unanswerable]),
        false_empty_rate=_share(answerable, [not run.kept(threshold, max_results) for run in answerable]),
    )


@dataclass(frozen=True)
class RelatedMetrics:
    """Custo e ganho de mostrar relacionados quando não há resposta direta."""
    related_threshold: float
    rescued: float  # com resposta, sem acerto direto, mas o trecho certo aparece nos relacionados
    unanswerable_with_related: float  # sem resposta, mas a tela mostra relacionados


def evaluate_related(
    runs: Sequence[QuestionRun], threshold: float, related_threshold: float, max_results: int, max_related: int
) -> RelatedMetrics:
    answerable_misses = [
        run for run in runs if not run.question.unanswerable and run.first_hit_rank(threshold, max_results) is None
    ]
    unanswerable = [run for run in runs if run.question.unanswerable]
    return RelatedMetrics(
        related_threshold=related_threshold,
        rescued=_share(answerable_misses, [
            any(is_hit(item, run.question) for item in _related(run, threshold, related_threshold, max_related))
            for run in answerable_misses
        ]),
        unanswerable_with_related=_share(unanswerable, [
            bool(_related(run, threshold, related_threshold, max_related)) for run in unanswerable
        ]),
    )


def _related(run: QuestionRun, threshold: float, related_threshold: float, max_related: int) -> list[ScoredCandidate]:
    if run.kept(threshold, max_results=1):
        return []
    return [item for item in run.ranked if item.score >= related_threshold][:max_related]


def sweep(runs: Sequence[QuestionRun], thresholds: Sequence[float], max_results: int) -> list[Metrics]:
    return [evaluate(runs, threshold, max_results) for threshold in thresholds]


def choose_threshold(results: Sequence[Metrics]) -> Metrics:
    """Maior equilíbrio e, entre os empatados, maior Recall@5. Se ainda sobra uma faixa de
    limiares equivalentes, fica com o do meio: longe das duas bordas, onde uma pergunta nova
    começaria a errar para um lado ou para o outro."""
    best_key = max(_quality(metrics) for metrics in results)
    tied = sorted((m for m in results if _quality(m) == best_key), key=lambda m: m.threshold)
    return tied[len(tied) // 2]


def _quality(metrics: Metrics) -> tuple[float, float]:
    return round(metrics.balance(), 6), round(metrics.recall_at_5, 6)


def _share(items: Sequence, flags: Sequence[bool]) -> float:
    return sum(flags) / len(items) if items else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
