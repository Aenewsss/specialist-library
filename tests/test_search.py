"""Busca contra o Postgres real, com embedder e reranker falsos (determinísticos, sem rede)."""
from datetime import date

import pytest

from app import catalog, speakers
from app.config import get_config
from app.ingest import repository
from app.ingest.models import Chunk, ContentMetadata, Diarization, SpeakerTurn
from app.search.hybrid import HybridSearcher
from app.search.models import SearchFilters
from app.search.service import SearchService

pytestmark = pytest.mark.db

DIMENSIONS = 1024
TOPICS = ["arca", "fóssil", "tsunami"]


class KeywordEmbedder:
    """Vetor one-hot pelo primeiro tópico que aparece no texto."""
    model_name = "fake"

    def embed(self, texts):
        return [self._vector(text) for text in texts]

    def _vector(self, text):
        vector = [0.0] * DIMENSIONS
        hits = [i for i, topic in enumerate(TOPICS) if topic in text.lower()]
        vector[hits[0] if hits else len(TOPICS)] = 1.0
        return vector


class OverlapReranker:
    """Nota = fração das palavras da pergunta que aparecem no trecho."""
    model_name = "fake"

    def score(self, question, passages):
        words = {w for w in question.lower().replace("?", "").split() if len(w) > 3}
        return [len(words & set(p.lower().split())) / len(words) for p in passages]


@pytest.fixture
def library(db):
    sergio = catalog.add_pessoa(db, "Sérgio Sacani")
    rodrigo = catalog.add_pessoa(db, "Rodrigo Silva")
    conteudo_id = catalog.add_youtube_video(db, "https://youtu.be/qgikRaQkPGU").conteudo_id
    chunks = [
        Chunk(0, 50, "a arca de Noé teria medidas enormes", "SPEAKER_02"),
        Chunk(50, 100, "marcas de tsunami em rochas antigas", "SPEAKER_00"),
        Chunk(100, 150, "um fóssil marinho no alto da montanha", "SPEAKER_00"),
        Chunk(150, 160, "fala do apresentador sobre a arca", "SPEAKER_01"),
    ]
    diarization = Diarization(
        turns=[SpeakerTurn(0, 1, label) for label in ("SPEAKER_00", "SPEAKER_01", "SPEAKER_02")],
        voice_embeddings={label: [1.0] * 256 for label in ("SPEAKER_00", "SPEAKER_01", "SPEAKER_02")},
    )
    embedder = KeywordEmbedder()
    with db.transaction():
        repository.save_metadata(db, conteudo_id, ContentMetadata("Debate", date(2025, 1, 16)))
        repository.save_diarization(db, conteudo_id, diarization)
        repository.replace_trechos(db, conteudo_id, chunks)
        trechos = repository.trechos_to_embed(db, conteudo_id)
        repository.save_embeddings(
            db, list(zip([i for i, _ in trechos], embedder.embed([t for _, t in trechos]))), "fake"
        )
    speakers.confirm_speaker(db, conteudo_id, "SPEAKER_00", sergio)
    speakers.confirm_speaker(db, conteudo_id, "SPEAKER_02", rodrigo)
    return {"sergio": sergio, "rodrigo": rodrigo}


def service():
    return SearchService(KeywordEmbedder(), OverlapReranker(), get_config())


def test_finds_the_right_trecho_with_person_and_timestamped_link(db, library):
    answer = service().ask(db, "o que ele diz sobre a arca de Noé?", threshold=0.3)

    top = answer["resultados"][0]
    assert top["pessoa"]["nome"] == "Rodrigo Silva"
    assert top["trechos"][0]["texto"] == "a arca de Noé teria medidas enormes"
    assert top["trechos"][0]["link"] == "https://www.youtube.com/watch?v=qgikRaQkPGU&t=0s"


def test_unattributed_speech_is_never_returned(db, library):
    searcher = HybridSearcher(db, KeywordEmbedder(), candidate_limit=50, rrf_k=60)

    candidates = searcher.search("arca", SearchFilters())

    assert "fala do apresentador sobre a arca" not in {c.texto for c in candidates}


def test_person_filter_restricts_results(db, library):
    searcher = HybridSearcher(db, KeywordEmbedder(), candidate_limit=50, rrf_k=60)

    candidates = searcher.search("arca", SearchFilters(pessoa_ids=[library["sergio"]]))

    assert candidates and {c.pessoa_nome for c in candidates} == {"Sérgio Sacani"}


def test_date_filter_excludes_older_content(db, library):
    searcher = HybridSearcher(db, KeywordEmbedder(), candidate_limit=50, rrf_k=60)

    assert searcher.search("arca", SearchFilters(published_from=date(2026, 1, 1))) == []


def test_question_without_answer_returns_not_found(db, library):
    answer = service().ask(db, "qual a opinião dele sobre criptomoedas?", threshold=0.3)

    assert answer["encontrado"] is False
