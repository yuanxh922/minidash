import pytest
from pathlib import Path

from app.database import get_db, get_db_connection, init_db, seed_db
from app.main import app
from tests.test_client import AsyncTestClient, SimpleTestClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client(tmp_path: Path):
    """Fixture that initializes a temporary SQLite test database and provides a test client."""
    test_db_path = str(tmp_path / "test_minidash.db")
    init_db(test_db_path)
    seed_db(test_db_path)

    def override_get_db():
        conn = get_db_connection(test_db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield SimpleTestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def async_client(tmp_path: Path):
    """Fixture that initializes a temporary SQLite test database and provides an async test client."""
    test_db_path = str(tmp_path / "test_minidash.db")
    init_db(test_db_path)
    seed_db(test_db_path)

    def override_get_db():
        conn = get_db_connection(test_db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield AsyncTestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def db_conn(tmp_path: Path):
    """Fixture that provides an isolated sqlite3 connection to the test database for direct DB queries."""
    test_db_path = str(tmp_path / "test_minidash.db")
    init_db(test_db_path)
    seed_db(test_db_path)
    conn = get_db_connection(test_db_path)
    try:
        yield conn
    finally:
        conn.close()

