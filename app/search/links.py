"""Link para o ponto exato da fonte. Montado na consulta, nunca gravado pronto."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePosition:
    fonte_tipo: str
    url_original: str
    external_id: str | None = None
    start_s: int | None = None
    page: int | None = None


def build_link(position: SourcePosition) -> str:
    builder = _BUILDERS.get(position.fonte_tipo, _plain_url)
    return builder(position)


def _youtube(position: SourcePosition) -> str:
    base = f"https://www.youtube.com/watch?v={position.external_id}"
    return f"{base}&t={position.start_s}s" if position.start_s is not None else base


def _book(position: SourcePosition) -> str:
    return f"{position.url_original}#page={position.page}" if position.page is not None else position.url_original


def _plain_url(position: SourcePosition) -> str:
    return position.url_original


# podcast_rss usa player próprio com seek; entra junto com o conector de podcast.
_BUILDERS = {"youtube": _youtube, "livro": _book}
