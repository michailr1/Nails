from __future__ import annotations

from app.client_models import MasterPublicProfile
from app.db import get_session_factory
from app.services.client_binding import create_master_link_token

CLIENT_KEY = "c" * 64


def _headers(telegram_user_id: int, *, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _token(master, display_name: str) -> str:
    with get_session_factory()() as session:
        session.add(
            MasterPublicProfile(
                owner_user_id=master.id,
                display_name=display_name,
            )
        )
        session.flush()
        link = create_master_link_token(session, owner_user_id=master.id)
        token = link.token
        session.commit()
        return token


def _start(client, telegram_user_id: int, token: str):
    return client.post(
        "/api/v1/client/start",
        headers=_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": "Анна"},
    )


def test_last_deep_link_becomes_sticky_but_masters_list_stays_explicit(
    client,
    create_user,
):
    master_a = create_user(telegram_user_id=830000001)
    master_b = create_user(telegram_user_id=830000002)
    token_a = _token(master_a, "Мастер А")
    token_b = _token(master_b, "Мастер Б")
    client_telegram_user_id = 930000001

    first = _start(client, client_telegram_user_id, token_a)
    assert first.status_code == 200
    binding_a = first.json()["master"]["binding_id"]

    second = _start(client, client_telegram_user_id, token_b)
    assert second.status_code == 200
    assert second.json()["master"]["display_name"] == "Мастер Б"

    resumed = client.get(
        "/api/v1/client/context",
        headers=_headers(client_telegram_user_id),
    )
    assert resumed.status_code == 200
    assert resumed.json()["state"] == "ready"
    assert resumed.json()["master"]["display_name"] == "Мастер Б"

    masters = client.get(
        "/api/v1/client/masters",
        headers=_headers(client_telegram_user_id),
    )
    assert masters.status_code == 200
    assert masters.json()["state"] == "choose_master"
    assert [item["display_name"] for item in masters.json()["masters"]] == [
        "Мастер А",
        "Мастер Б",
    ]

    selected = client.post(
        "/api/v1/client/context/select",
        headers=_headers(client_telegram_user_id, binding_id=binding_a),
    )
    assert selected.status_code == 200
    assert selected.json()["master"]["display_name"] == "Мастер А"

    resumed_again = client.get(
        "/api/v1/client/context",
        headers=_headers(client_telegram_user_id),
    )
    assert resumed_again.status_code == 200
    assert resumed_again.json()["master"]["display_name"] == "Мастер А"


def test_foreign_client_cannot_select_another_clients_binding(client, create_user):
    master = create_user(telegram_user_id=830000003)
    token = _token(master, "Мастер В")
    owner_client = 930000002
    other_client = 930000003

    started = _start(client, owner_client, token)
    assert started.status_code == 200
    binding_id = started.json()["master"]["binding_id"]

    response = client.post(
        "/api/v1/client/context/select",
        headers=_headers(other_client, binding_id=binding_id),
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_binding_not_found"
