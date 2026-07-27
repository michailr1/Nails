from __future__ import annotations

from app.client_models import MasterPublicProfile
from app.db import get_session_factory
from app.services.client_binding import create_master_link_token

CLIENT_KEY = "c" * 64
INTERNAL_KEY = "i" * 64


def _client_headers(telegram_user_id: int, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _internal_headers() -> dict[str, str]:
    return {"X-Nails-Internal-Key": INTERNAL_KEY}


def _token(master, display_name: str, public_contact: str | None = None) -> str:
    with get_session_factory()() as session:
        session.add(
            MasterPublicProfile(
                owner_user_id=master.id,
                display_name=display_name,
                public_contact=public_contact,
            )
        )
        session.flush()
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
        return token


def _start(client, telegram_user_id: int, token: str):
    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": "Анна"},
    )
    assert response.status_code == 200
    return response.json()


def test_free_text_without_public_contact_is_queued_and_claimed_privately(
    client,
    create_user,
):
    master = create_user(telegram_user_id=840000001)
    token = _token(master, "Мастер А")
    telegram_user_id = 940000001
    started = _start(client, telegram_user_id, token)
    binding_id = started["master"]["binding_id"]

    queued = client.post(
        "/api/v1/client/contact-forward",
        headers=_client_headers(telegram_user_id, binding_id),
        json={"message_text": "Можно завтра после шести?"},
    )
    assert queued.status_code == 200
    assert queued.json() == {"accepted": True, "message": "Передам мастеру."}
    assert str(master.telegram_user_id) not in str(queued.json())

    claim = client.post(
        "/api/v1/client/contact-forward/internal/claim",
        headers=_internal_headers(),
    )
    assert claim.status_code == 200
    payload = claim.json()
    assert payload["claimed"] is True
    assert payload["master_telegram_user_id"] == master.telegram_user_id
    assert payload["client_public_name"] == "Анна"
    assert payload["message_text"] == "Можно завтра после шести?"

    ack = client.post(
        "/api/v1/client/contact-forward/internal/ack",
        headers=_internal_headers(),
        json={"claim_id": payload["claim_id"], "sent": True},
    )
    assert ack.status_code == 200
    assert ack.json() == {"changed": True, "sent": True}

    empty = client.post(
        "/api/v1/client/contact-forward/internal/claim",
        headers=_internal_headers(),
    )
    assert empty.status_code == 200
    assert empty.json()["claimed"] is False


def test_public_contact_is_opt_in_and_disables_structured_forward(client, create_user):
    master = create_user(telegram_user_id=840000002)
    token = _token(master, "Мастер Б", "@master_b")
    telegram_user_id = 940000002
    started = _start(client, telegram_user_id, token)
    assert started["master"]["public_contact"] == "@master_b"
    binding_id = started["master"]["binding_id"]

    response = client.post(
        "/api/v1/client/contact-forward",
        headers=_client_headers(telegram_user_id, binding_id),
        json={"message_text": "Хочу уточнить запись"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "client_public_contact_available"


def test_foreign_binding_cannot_queue_forward(client, create_user):
    master = create_user(telegram_user_id=840000003)
    token = _token(master, "Мастер В")
    owner_client = 940000003
    started = _start(client, owner_client, token)
    binding_id = started["master"]["binding_id"]

    response = client.post(
        "/api/v1/client/contact-forward",
        headers=_client_headers(940000004, binding_id),
        json={"message_text": "Чужой контекст"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_binding_not_found"


def test_internal_claim_is_not_accessible_with_client_key(client):
    response = client.post(
        "/api/v1/client/contact-forward/internal/claim",
        headers={"X-Nails-Client-Internal-Key": CLIENT_KEY},
    )
    assert response.status_code == 401
