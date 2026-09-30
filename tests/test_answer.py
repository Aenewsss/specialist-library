from datetime import date
from uuid import uuid4

from app.search.answer import AnswerRules, build_answer
from app.search.hybrid import reciprocal_rank_fusion
from app.search.models import Candidate, ScoredCandidate

RULES = AnswerRules(threshold=0.5, max_results=10)
SERGIO, RODRIGO = uuid4(), uuid4()


def candidate(pessoa_id, nome, texto, inicio_s=754):
    return Candidate(
        trecho_id=uuid4(), texto=texto, inicio_s=inicio_s, fim_s=inicio_s + 50, pagina=None,
        pessoa_id=pessoa_id, pessoa_nome=nome, pessoa_areas=[], conteudo_titulo="Debate",
        publicado_em=date(2025, 1, 16), url_original="https://www.youtube.com/watch?v=qgikRaQkPGU",
        external_id="qgikRaQkPGU", fonte_tipo="youtube",
    )


def test_rrf_rewards_items_ranked_well_in_both_lists():
    a, b, c = uuid4(), uuid4(), uuid4()

    fused = reciprocal_rank_fusion([[a, b, c], [b, c]], k=60)

    assert fused == [b, c, a]


def test_nothing_above_threshold_means_not_found():
    scored = [ScoredCandidate(candidate(SERGIO, "Sérgio", "algo"), 0.2)]

    answer = build_answer("pergunta?", scored, RULES)

    assert answer == {"pergunta": "pergunta?", "encontrado": False, "resultados": []}


def test_groups_by_pessoa_ordered_by_best_score_with_literal_text_and_link():
    scored = [
        ScoredCandidate(candidate(SERGIO, "Sérgio", "texto do Sérgio", inicio_s=30), 0.7),
        ScoredCandidate(candidate(RODRIGO, "Rodrigo", "texto do Rodrigo"), 0.9),
        ScoredCandidate(candidate(SERGIO, "Sérgio", "outro do Sérgio"), 0.6),
    ]

    answer = build_answer("pergunta?", scored, RULES)

    assert [group["pessoa"]["nome"] for group in answer["resultados"]] == ["Rodrigo", "Sérgio"]
    sergio_trechos = answer["resultados"][1]["trechos"]
    assert [t["texto"] for t in sergio_trechos] == ["texto do Sérgio", "outro do Sérgio"]
    assert sergio_trechos[0]["link"] == "https://www.youtube.com/watch?v=qgikRaQkPGU&t=30s"
    assert sergio_trechos[0]["publicado_em"] == "2025-01-16"


def test_limits_number_of_results():
    scored = [ScoredCandidate(candidate(SERGIO, "Sérgio", f"t{i}"), 0.9) for i in range(20)]

    answer = build_answer("pergunta?", scored, AnswerRules(threshold=0.5, max_results=3))

    assert len(answer["resultados"][0]["trechos"]) == 3
