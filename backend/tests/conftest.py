import os
import uuid

os.environ["DEMOS_DATABASE_URL"] = "postgresql://demos:demos_dev@127.0.0.1:5433/demos_test"
os.environ["DEMOS_IDENTITY_DATABASE_URL"] = "postgresql://demos:demos_dev@127.0.0.1:5433/demos_identity_test"
os.environ["DEMOS_SAMPLE_DATA"] = "1"
os.environ["DEMOS_DEV_IDENTITY"] = "1"
# Keep test runs out of the dev logs people copy off the VM.
os.environ["DEMOS_LOG_DIR"] = "logs/test"
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest

from demos.db import connect, migrate
from demos.seed import seed


@pytest.fixture(scope="session")
def seeded():
    with connect() as conn:
        migrate(conn)
        seed(conn)


@pytest.fixture
def conn(seeded):
    """Each test runs in a transaction that's undone afterwards."""
    with connect() as c:
        real_commit = c.commit
        c.commit = lambda: None
        yield c
        c.commit = real_commit
        c.rollback()


@pytest.fixture
def person(conn):
    pid = uuid.uuid4()
    conn.execute("INSERT INTO person (id, language) VALUES (%s, 'en')", (pid,))
    return conn.execute("SELECT * FROM person WHERE id = %s", (pid,)).fetchone()
