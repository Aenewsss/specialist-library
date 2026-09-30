from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import PROJECT_ROOT, get_config

MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def connect(database_url: str | None = None, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(database_url or get_config().database_url, row_factory=dict_row, autocommit=autocommit)


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Aplica, em ordem de nome, os .sql ainda não registrados. Devolve os aplicados."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " nome text PRIMARY KEY, aplicada_em timestamptz NOT NULL DEFAULT now())"
    )
    already_applied = {row["nome"] for row in conn.execute("SELECT nome FROM schema_migrations")}
    newly_applied = []
    for sql_file in sorted(migrations_dir.glob("*.sql")):
        if sql_file.name in already_applied:
            continue
        with conn.transaction():
            conn.execute(sql_file.read_text())
            conn.execute("INSERT INTO schema_migrations (nome) VALUES (%s)", (sql_file.name,))
        newly_applied.append(sql_file.name)
    conn.commit()
    return newly_applied
