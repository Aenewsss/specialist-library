import json
import logging
from uuid import UUID

import typer
from dotenv import load_dotenv

from app import catalog, speakers
from app.config import PROJECT_ROOT, get_config
from app.db import apply_migrations, connect
from app.ingest.connectors.youtube import InvalidYoutubeUrl
from app.ingest.models import PIPELINE_STAGES

load_dotenv(PROJECT_ROOT / ".env")
app = typer.Typer(help="Biblioteca de Especialistas", no_args_is_help=True)


@app.command()
def migrate() -> None:
    """Aplica as migrations pendentes."""
    with connect() as conn:
        applied = apply_migrations(conn)
    typer.echo(f"Aplicadas: {', '.join(applied)}" if applied else "Nenhuma migration pendente.")


@app.command("add-pessoa")
def add_pessoa(nome: str, bio: str = typer.Option(None, help="Bio curta")) -> None:
    """Cadastra um especialista e imprime o id."""
    with connect() as conn:
        pessoa_id = catalog.add_pessoa(conn, nome, bio)
    typer.echo(pessoa_id)


@app.command("add-video")
def add_video(
    url: str,
    dono: UUID = typer.Option(None, help="Pessoa dona do canal, se houver (não define quem fala)"),
) -> None:
    """Registra um vídeo do YouTube e enfileira a ingestão."""
    try:
        with connect() as conn:
            registered = catalog.add_youtube_video(conn, url, dono)
    except (InvalidYoutubeUrl, catalog.PessoaNotFound) as error:
        _fail(error)
    status = "registrado" if registered.created else "já existia"
    typer.echo(f"Vídeo {registered.video_id} {status}: conteudo_id={registered.conteudo_id}")


@app.command()
def ingest() -> None:
    """Roda a fila de ingestão até não sobrar etapa executável."""
    from app.ingest.stages import IngestionStages, PipelineServices
    from app.ingest.worker import run_until_empty

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # downloads do Hugging Face poluem o log
    config = get_config()
    with connect(autocommit=True) as conn:
        report = run_until_empty(conn, IngestionStages(conn, PipelineServices(config), config))
    typer.echo(f"Etapas ok: {len(report.succeeded)} · com erro: {len(report.failed)}")
    for job, error in report.failed:
        typer.echo(f"  {job.etapa} ({job.conteudo_id}): {error}", err=True)


@app.command()
def reprocessar(
    conteudo_id: UUID,
    a_partir_de: str = typer.Option(None, help=f"Esta etapa e as seguintes: {', '.join(PIPELINE_STAGES)}"),
    somente: list[str] = typer.Option([], help="Só estas etapas (repetível), ex.: --somente transcricao"),
) -> None:
    """Volta etapas para 'pendente'. Rode `ingest` depois."""
    from app.ingest.worker import restart_from, restart_only

    chosen = [a_partir_de] if a_partir_de else somente
    unknown = [etapa for etapa in chosen if etapa not in PIPELINE_STAGES]
    if not chosen or unknown:
        _fail(ValueError(f"Informe --a-partir-de ou --somente com etapas válidas: {', '.join(PIPELINE_STAGES)}"))
    with connect() as conn:
        if a_partir_de:
            restart_from(conn, conteudo_id, a_partir_de)
        else:
            restart_only(conn, conteudo_id, somente)
        conn.commit()
    typer.echo(f"Voltaram para pendente: {', '.join(chosen)}{' e seguintes' if a_partir_de else ''}.")


@app.command()
def falantes(conteudo_id: UUID) -> None:
    """Lista as vozes de um conteúdo, com links para ouvir e a atribuição atual."""
    with connect() as conn:
        summaries = speakers.list_speakers(conn, conteudo_id)
    for summary in summaries:
        who = "ignorado" if summary.ignored else summary.pessoa_nome or "— não atribuído —"
        state = "confirmado" if summary.confirmed else _confidence_text(summary.confidence)
        typer.echo(f"\n{summary.label}  {summary.speaking_seconds / 60:.1f} min  →  {who} ({state})")
        for link in summary.sample_links:
            typer.echo(f"    {link}")


@app.command("rotular-falante")
def rotular_falante(conteudo_id: UUID, rotulo: str, pessoa: UUID = typer.Option(...)) -> None:
    """Confirma quem é a voz; a voz vira amostra para reconhecer a pessoa em outros vídeos."""
    try:
        with connect() as conn:
            speakers.confirm_speaker(conn, conteudo_id, rotulo, pessoa)
    except speakers.SpeakerNotFound as error:
        _fail(error)
    typer.echo(f"{rotulo} confirmado.")


@app.command("ignorar-falante")
def ignorar_falante(conteudo_id: UUID, rotulo: str) -> None:
    """Descarta uma voz irrelevante (ex.: apresentador): os trechos dela saem da busca."""
    try:
        with connect() as conn:
            removed = speakers.ignore_speaker(conn, conteudo_id, rotulo)
    except speakers.SpeakerNotFound as error:
        _fail(error)
    typer.echo(f"{rotulo} ignorado; {removed} trechos removidos.")


@app.command()
def serve(reload: bool = typer.Option(False, help="Recarrega ao editar o código (dev)")) -> None:
    """Sobe a API com os modelos carregados uma única vez."""
    import uvicorn

    api = get_config().api
    uvicorn.run("app.api:app", host=api.host, port=api.port, reload=reload)


@app.command()
def ask(
    pergunta: str,
    pessoa: list[UUID] = typer.Option([], help="Restringe a uma ou mais pessoas"),
    como_json: bool = typer.Option(False, "--json", help="Imprime a resposta no formato da API"),
) -> None:
    """Pergunta à biblioteca (via API): trechos literais com link para o momento exato."""
    from app import client

    try:
        answer = client.ask(get_config().api.url, pergunta, pessoa)
    except client.ApiUnavailable as error:
        _fail(error)
    if como_json:
        typer.echo(json.dumps(answer, ensure_ascii=False, indent=2))
        return
    _print_answer(answer)


def _print_answer(answer: dict) -> None:
    if answer["encontrado"]:
        _print_groups(answer["resultados"])
        return
    if answer.get("relacionados"):
        typer.echo("Nenhuma resposta direta. Estes trechos podem estar relacionados (baixa confiança):")
        _print_groups(answer["relacionados"])
        return
    typer.echo("Ninguém na biblioteca falou sobre isso.")


def _print_groups(groups: list[dict]) -> None:
    for group in groups:
        typer.echo(f"\n■ {group['pessoa']['nome']}")
        for trecho in group["trechos"]:
            typer.echo(f"  [{trecho['nota_reranker']:.2f}] {trecho['conteudo_titulo']} ({trecho['publicado_em']})")
            typer.echo(f"  {trecho['link']}")
            typer.echo(f"  “{trecho['texto']}”\n")


def _confidence_text(confidence: float | None) -> str:
    return "sem comparação: pouca fala ou nenhuma amostra de voz" if confidence is None else f"similaridade {confidence:.2f}"


def _fail(error: Exception) -> None:
    typer.echo(f"Erro: {error}", err=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
