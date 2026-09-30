from dataclasses import replace

import pytest

from app.evaluation import (
    QuestionRun, TestQuestion, choose_threshold, evaluate, evaluate_related, is_hit, load_questions,
)
from app.search.models import ScoredCandidate
from tests.test_answer import RODRIGO, SERGIO, candidate

ARCA = TestQuestion("onde a arca pousou?", "qgikRaQkPGU", "Rodrigo Silva", ((1327, 1357),))
CRIPTO = TestQuestion("criptomoedas?", unanswerable=True)


def scored(pessoa_id, nome, inicio_s, score):
    return ScoredCandidate(candidate(pessoa_id, nome, "texto", inicio_s=inicio_s), score)


def test_hit_requires_overlap_and_the_right_person():
    assert is_hit(scored(RODRIGO, "Rodrigo Silva", 1300, 0.9), ARCA)  # 1300–1350 sobrepõe
    assert not is_hit(scored(RODRIGO, "Rodrigo Silva", 1400, 0.9), ARCA)
    assert not is_hit(scored(SERGIO, "Sérgio Sacani", 1300, 0.9), ARCA)


def test_metrics_at_a_threshold():
    runs = [
        QuestionRun(ARCA, [scored(SERGIO, "Sérgio Sacani", 0, 0.8), scored(RODRIGO, "Rodrigo Silva", 1300, 0.6)]),
        QuestionRun(CRIPTO, [scored(SERGIO, "Sérgio Sacani", 0, 0.1)]),
    ]

    metrics = evaluate(runs, threshold=0.5, max_results=10)

    assert (metrics.recall_at_5, metrics.mrr) == (1.0, 0.5)
    assert (metrics.not_found_precision, metrics.false_empty_rate) == (1.0, 0.0)


def test_threshold_too_high_turns_answers_into_false_empties():
    runs = [QuestionRun(ARCA, [scored(RODRIGO, "Rodrigo Silva", 1300, 0.3)])]

    metrics = evaluate(runs, threshold=0.5, max_results=10)

    assert (metrics.recall_at_5, metrics.false_empty_rate) == (0.0, 1.0)


def test_chooses_the_threshold_that_balances_both_error_types():
    runs = [
        QuestionRun(ARCA, [scored(RODRIGO, "Rodrigo Silva", 1300, 0.4)]),
        QuestionRun(CRIPTO, [scored(SERGIO, "Sérgio Sacani", 0, 0.2)]),
    ]
    results = [evaluate(runs, t, 10) for t in (0.1, 0.3, 0.5)]

    assert choose_threshold(results).threshold == 0.3


def test_loads_single_and_multiple_intervals(tmp_path):
    path = tmp_path / "perguntas.yaml"
    path.write_text(
        "- pergunta: a\n  resposta_entre_s: [1, 2]\n"
        "- pergunta: b\n  resposta_entre_s: [[1, 2], [5, 6]]\n"
        "- pergunta: c\n  sem_resposta: true\n"
    )

    a, b, c = load_questions(path)

    assert a.intervals == ((1, 2),) and b.intervals == ((1, 2), (5, 6)) and c.unanswerable


def test_real_question_file_is_valid():
    from app.config import PROJECT_ROOT

    questions = load_questions(PROJECT_ROOT / "eval" / "perguntas.yaml")

    assert sum(q.unanswerable for q in questions) >= 5
    assert all(q.intervals for q in questions if not q.unanswerable)


def test_picks_the_middle_of_a_plateau_of_equivalent_thresholds():
    runs = [
        QuestionRun(ARCA, [scored(RODRIGO, "Rodrigo Silva", 1300, 0.9)]),
        QuestionRun(CRIPTO, [scored(SERGIO, "Sérgio Sacani", 0, 0.1)]),
    ]
    results = [evaluate(runs, t, 10) for t in (0.2, 0.4, 0.6, 0.8)]  # todos perfeitos

    assert choose_threshold(results).threshold == 0.6


def test_related_metrics_measure_rescues_and_noise():
    runs = [
        QuestionRun(ARCA, [scored(RODRIGO, "Rodrigo Silva", 1300, 0.3)]),  # sem acerto direto, resgatável
        QuestionRun(CRIPTO, [scored(SERGIO, "Sérgio Sacani", 0, 0.2)]),
    ]

    metrics = evaluate_related(runs, threshold=0.4, related_threshold=0.15, max_results=10, max_related=3)

    assert (metrics.rescued, metrics.unanswerable_with_related) == (1.0, 1.0)
    assert evaluate_related(runs, 0.4, 0.25, 10, 3).unanswerable_with_related == 0.0
