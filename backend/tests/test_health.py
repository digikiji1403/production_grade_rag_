from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app.main import app
from backend.app.db.dependencies import get_db


client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "healthy",
        "service": "RAGForge API",
        "version": "0.1.0",
    }


def test_api_documentation_available():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/health/ready" in schema["paths"]


def test_readiness_check_database_connected():
    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    assert response.json() == {
        "status": "ready",
        "database": "connected",
    }

    mock_db.execute.assert_called_once()


def test_readiness_check_database_unavailable():
    mock_db = MagicMock()
    mock_db.execute.side_effect = SQLAlchemyError("Database connection failed")

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503

    assert response.json() == {
        "detail": {
            "status": "not_ready",
            "database": "unavailable",
        }
    }