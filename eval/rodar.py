"""Roda o conjunto de teste, varre limiares e grava o resultado em eval/resultados/.

    .venv/bin/python eval/rodar.py                  # mede e recomenda um limiar
    .venv/bin/python eval/rodar.py --gravar-limiar  # também grava o limiar em config.yaml
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import CONFIG_PATH, PROJECT_ROOT, get_config  # noqa: E402
from app.db import connect  # noqa: E402
from app.evaluation import (  # noqa: E402
    RECALL_AT, Metrics, QuestionRun, choose_threshold, evaluate, is_hit, load_questions, sweep,
)
from app.search.models import SearchFilters  # noqa: E402
from app.search.service import build_search_service  # noqa: E402

EVAL_DIR = PROJECT_ROOT / "eval"
THRESHOLDS = [round(step * 0.05, 2) for step in range(0, 20)]


def main() -> None:
    args = _parse_args()
    config = get_config()
    questions = load_questions(args.perguntas)
    runs = _score_all(questions, config)

    max_results = config.busca.top_reranker
    results = sweep(runs, THRESHOLDS, max_results)
    current = evaluate(runs, config.busca.limiar_reranker, max_results)
    best = choose_threshold(results)

    _print_sweep(results, current, best)
    _print_misses(runs, best.threshold, max_results)
    output = _save(runs, results, current, best, config, max_results)
    print(f"\nResultado gravado em {output.relative_to(PROJECT_ROOT)}")
    if args.gravar_limiar:
        _write_threshold(best.threshold)
        print(f"limiar_reranker = {best.threshold} gravado em config.yaml")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--perguntas", type=Path, default=EVAL_DIR / "perguntas.yaml")
    parser.add_argument("--gravar-limiar", action="store_true", help="Grava o limiar recomendado no config.yaml")
    return parser.parse_args()


def _score_all(questions, config) -> list[QuestionRun]:
    service = build_search_service(config)
    runs = []
    with connect() as conn:
        for index, question in enumerate(questions, start=1):
            print(f"\r{index}/{len(questions)} perguntas", end="", flush=True)
            scored = service.score_candidates(conn, question.question, SearchFilters())
            runs.append(QuestionRun(question, sorted(scored, key=lambda item: item.score, reverse=True)))
    print()
    return runs


def _print_sweep(results: list[Metrics], current: Metrics, best: Metrics) -> None:
    print(f"\n{'limiar':>6} {'Recall@' + str(RECALL_AT):>9} {'MRR':>6} {'não enc.':>9} {'falso vazio':>12}")
    for metrics in [*results, current]:
        marker = " ← recomendado" if metrics is best else " ← atual (config)" if metrics is current else ""
        print(
            f"{metrics.threshold:>6.2f} {metrics.recall_at_5:>9.0%} {metrics.mrr:>6.2f}"
            f" {metrics.not_found_precision:>9.0%} {metrics.false_empty_rate:>12.0%}{marker}"
        )


def _print_misses(runs: list[QuestionRun], threshold: float, max_results: int) -> None:
    print(f"\nErros no limiar {threshold}:")
    for run in runs:
        kept = run.kept(threshold, max_results)
        if run.question.unanswerable:
            if kept:
                print(f"  ✗ sem resposta, mas voltou {len(kept)} trecho(s): {run.question.question}")
            continue
        rank = run.first_hit_rank(threshold, max_results)
        if rank is None or rank > RECALL_AT:
            where = "vazio" if not kept else f"acerto na posição {rank}" if rank else "nenhum acerto"
            best_hit = next((item for item in run.ranked if is_hit(item, run.question)), None)
            hint = f" (melhor trecho certo teve nota {best_hit.score:.3f})" if best_hit else " (trecho certo nem virou candidato)"
            print(f"  ✗ {where}{hint}: {run.question.question}")


def _save(runs, results, current, best, config, max_results) -> Path:
    label = f"{config.modelos.embedding.split('/')[-1]}_{config.modelos.reranker.split('/')[-1]}"
    label += f"_chunk{config.chunk.duracao_min_s}-{config.chunk.duracao_max_s}"
    output = EVAL_DIR / "resultados" / f"{datetime.now():%Y-%m-%d_%H%M}-{label}.json"
    output.write_text(json.dumps({
        "config": config.model_dump(mode="json", include={"modelos", "chunk", "busca"}),
        "limiar_recomendado": best.__dict__,
        "limiar_atual": current.__dict__,
        "varredura": [metrics.__dict__ for metrics in results],
        "perguntas": [_question_detail(run, best.threshold, max_results) for run in runs],
    }, ensure_ascii=False, indent=2))
    return output


def _question_detail(run: QuestionRun, threshold: float, max_results: int) -> dict:
    return {
        "pergunta": run.question.question,
        "sem_resposta": run.question.unanswerable,
        "posicao_primeiro_acerto": run.first_hit_rank(threshold, max_results),
        "top5": [
            {"nota": round(item.score, 4), "pessoa": item.candidate.pessoa_nome,
             "inicio_s": item.candidate.inicio_s, "fim_s": item.candidate.fim_s, "acerto": is_hit(item, run.question)}
            for item in run.ranked[:RECALL_AT]
        ],
    }


def _write_threshold(threshold: float) -> None:
    text = CONFIG_PATH.read_text()
    updated = re.sub(r"(limiar_reranker:\s*)[0-9.]+(.*)", rf"\g<1>{threshold}  # calibrado por eval/rodar.py", text)
    CONFIG_PATH.write_text(updated)


if __name__ == "__main__":
    main()
