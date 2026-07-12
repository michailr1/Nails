from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import main


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ok_when_database_responds(client: TestClient, monkeypatch) -> None:
    connection = MagicMock()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    engine = MagicMock()
    engine.connect.return_value = context_manager
    monkeypatch.setattr(main, "get_engine", lambda: engine)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    connection.execute.assert_called_once()


def test_ready_returns_503_when_database_is_unavailable(client: TestClient, monkeypatch) -> None:
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("down"))
    monkeypatch.setattr(main, "get_engine", lambda: engine)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
