# DATABASE_URL must be set before any `db.*` or `main` import — db/db.py and
# alembic/env.py both read it at import time via os.environ["DATABASE_URL"].
import os
import socket
import subprocess
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://my_dev_user:my_dev_password@localhost:5432/citywatch_test"
)

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

REPO_ROOT = Path(__file__).resolve().parent.parent

# Loopback Postgres is the only outbound connection tests are allowed to make.
_ALLOWED_ADDRESSES = {("127.0.0.1", 5432), ("localhost", 5432), ("::1", 5432)}
_real_connect = socket.socket.connect


def _guarded_connect(self, address, *args, **kwargs):
    if isinstance(address, str):  # AF_UNIX
        return _real_connect(self, address, *args, **kwargs)
    if address[:2] in _ALLOWED_ADDRESSES:
        return _real_connect(self, address, *args, **kwargs)
    raise OSError(f"blocked outbound network connection to {address!r} during tests")


@pytest.fixture(scope="session", autouse=True)
def _block_network():
    """Fails any Gemini/Geoapify call loudly instead of letting a missing mock hit the network."""
    socket.socket.connect = _guarded_connect
    yield
    socket.socket.connect = _real_connect


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=REPO_ROOT,
        env={**os.environ},
    )


@pytest.fixture(scope="session", autouse=True)
def _seeded_corpus(_migrate):
    """Seeds the 172-marker corpus once, committed, before any per-test transaction opens.

    db.seed.seed() opens and commits its own Session(engine), so it cannot run
    inside a per-test transaction — it has to happen here, once per session.
    """
    from db.seed import seed

    seed(force=True)


@pytest.fixture
def db_session():
    from db.db import engine

    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint lets route-level session.commit() calls land on a savepoint
    # instead of ending the outer transaction, so the rollback below really undoes them.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    from db.db import get_session
    from main import app

    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
