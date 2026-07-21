from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_client_section_exposes_create_and_archive_actions(client, clean_database):
    response = client.get("/web/web-client-cards.js")

    assert response.status_code == 200
    assert 'id="add-client"' in response.text
    assert 'Добавить клиентку' in response.text
    assert 'api("/web/api/clients", { method: "POST"' in response.text
    assert 'id="client-card-archive"' in response.text
    assert 'method: "POST"' in response.text
    assert '/archive`' in response.text
    assert 'История записей сохранится' in response.text
    assert 'window.confirm(`Отправить' in response.text


def test_client_archive_endpoint_reuses_existing_profile_status():
    api = (ROOT / "backend/app/api/web_read.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/app/services/scheduling_clients.py").read_text(
        encoding="utf-8"
    )

    assert '@router.post("/clients/{client_id}/archive"' in api
    assert "validate_web_boundary(request)" in api
    assert "archive_client(session, identity, client_id)" in api
    assert "Client.profile_status == ClientProfileStatus.active" in service
    assert "client.profile_status = ClientProfileStatus.archived" in service
    assert 'action="client.archived"' in service
    assert "session.commit()" in service


def test_archive_flow_does_not_delete_client_or_booking_history():
    service = (ROOT / "backend/app/services/scheduling_clients.py").read_text(
        encoding="utf-8"
    )

    archive_body = service.split("def archive_client(", 1)[1]
    assert "session.delete" not in archive_body
    assert "Booking" not in archive_body
