from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings

SCHEMA = Path(__file__).with_name("schema.sql")
IDENTITY_SCHEMA = Path(__file__).with_name("identity_schema.sql")


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or settings().database_url, row_factory=dict_row)


def migrate(conn: psycopg.Connection, path: Path = SCHEMA) -> None:
    conn.execute(path.read_text())
    conn.commit()
