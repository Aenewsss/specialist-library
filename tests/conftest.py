from urllib.parse import urlparse, urlunparse

import psycopg
import pytest

from app.config import get_config
from app.db import apply_migrations, connect

TEST_DATABASE_NAME = "biblioteca_test"


def _with_database(url: str, database: str) -> str:
    return urlunparse(urlparse(url)._replace(path=f"/{database}"))


@pytest.fixture(scope="session")
def test_database_url():
    base_url = get_config().database_url
    try:
        admin = psycopg.connect(base_url, autocommit=True)
    except psycopg.OperationalError:
        pytest.skip("Postgres indisponível: rode `docker compose up -d`")
    with admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME}")
        admin.execute(f"CREATE DATABASE {TEST_DATABASE_NAME}")
    url = _with_database(base_url, TEST_DATABASE_NAME)
    with connect(url) as conn:
        apply_migrations(conn)
    return url


@pytest.fixture
def db(test_database_url):
    with connect(test_database_url) as conn:
        yield conn
        conn.rollback()
        conn.execute("TRUNCATE pessoa, fonte, conteudo, trecho, job_ingestao, area, amostra_voz CASCADE")
        conn.commit()
