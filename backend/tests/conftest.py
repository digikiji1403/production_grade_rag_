
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.dependencies import get_db
from backend.app.db.session import engine
from backend.app.main import app


@pytest.fixture
def db_session():
    # Never run integration tests against the development database.
    if engine.url.database != "ragforge_test":
        pytest.fail(
            f"Tests require ragforge_test, "
            f"but connected to {engine.url.database}"
        )

    connection = engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
