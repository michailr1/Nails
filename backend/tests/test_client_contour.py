from __future__ import annotations

import os
import uuid

from app.client_models import ClientTelegramIdentity, MasterPublicProfile
from app.db import get_session_factory
from app.services.client_binding import create_master_link_token

CLIENT_KEY = "c" * 64
os.environ.setdefault("CLIENT_API_ENABLED", "true")
os.environ.setdefault("CLIENT_INTERNAL_API_KEY", CLIENT_KEY)

NO_BINDING_MESSAGE = (
    "👋 Здравствуйте! Это бот для записи к мастеру. Запись открывается по личной "
    "ссылке вашего мастера — обычно она в его профиле, сторис или визитке. "
    "Откройте эту ссылку — и я покажу запись именно к вашему мастеру. Если "
    "ссылки нет — попросите у мастера «ссылку для записи»."
)
INVALID_LINK_MESSAGE = (
    "Эта ссылка больше не действует. Попросите у мастера актуальную ссылку "
    "для записи 🙏"
)
REVOKED_MESSAGE = (
    "Запись к этому мастеру сейчас недоступна. Если это ошибка — свяжитесь "
    "с мастером напрямую."
)


def _headers(telegram_user_id: int, *, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _master_link(master, name: str, contact: str | None = None) -> str:
    with get_session_factory()() as session:
        session.add(
            MasterPublicProfile(
                owner_user_id=master.id,
                display_name=name,
                public_contact=contact,
            )
        )
        session.flush()
        link = create_master_link_token(session, owner_user_id=master.id)
        token = link.token
        session.commit()
        return token


def _start(client, telegram_user_id: int, token: str, name: str = "Анна"):
    return client.post(
        "/api/v1/client/start",
        headers=_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": name},
    )


def test_cold_entry_without_binding_uses_exact_adr009_text(client):
    response = client.get("/api/v1/client/context", headers=_headers(920000001))
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "no_binding"
    assert payload["message"] == NO_BINDING_MESSAGE
    assert payload["master"] is None
    assert payload["masters"] == []


def test_client_api_rejects_missing_internal_key(client):
    response = client.get(
        "/api/v1/client/context",
        headers={"X-Telegram-User-ID": "920000002"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_start_token_resolves_owner_and_never_projects_master_telegram_id(
    client,
    create_user,
):
    master = create_user(telegram_user_id=820000001)
    token = _master_link(master, "Ногти у Насти", "@nails_nastya")

    response = _start(client, 920000003, token)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "ready"
    assert payload["message"] == (
        "👋 Здравствуйте! Вы записываетесь к **Ногти у Насти**.\n"
        "[💅 Прайс] [📅 Записаться] [🗂 Мои записи]"
    )
    assert payload["master"]["display_name"] == "Ногти у Насти"
    assert payload["master"]["public_contact"] == "@nails_nastya"
    assert "telegram_user_id" not in payload["master"]
    assert str(master.telegram_user_id) not in str(payload)


def test_start_body_cannot_override_owner(client, create_user):
    master = create_user(telegram_user_id=820000002)
    token = _master_link(master, "Мастер А")
    response = client.post(
        "/api/v1/client/start",
        headers=_headers(920000004),
        json={
            "start_token": token,
            "requested_public_name": "Анна",
            "owner_user_id": str(master.id),
        },
    )
    assert response.status_code == 422


def test_invalid_link_uses_exact_adr009_text(client):
    response = _start(client, 920000005, "missing-token")
    assert response.status_code == 200
    assert response.json() == {
        "state": "invalid_link",
        "message": INVALID_LINK_MESSAGE,
        "master": None,
        "masters": [],
    }


def test_revoked_binding_uses_exact_adr009_text(client, create_user):
    master = create_user(telegram_user_id=820000003)
    token = _master_link(master, "Мастер Б")
    first = _start(client, 920000006, token)
    assert first.status_code == 200
    binding_id = uuid.UUID(first.json()["master"]["binding_id"])

    with get_session_factory()() as session:
        row = session.get(ClientTelegramIdentity, binding_id)
        assert row is not None
        row.status = "revoked"
        session.commit()

    response = _start(client, 920000006, token)
    assert response.status_code == 200
    assert response.json()["state"] == "revoked"
    assert response.json()["message"] == REVOKED_MESSAGE


def test_multi_binding_menu_contains_only_callers_own_masters(client, create_user):
    master_a = create_user(telegram_user_id=820000004)
    master_b = create_user(telegram_user_id=820000005)
    token_a = _master_link(master_a, "Мастер А")
    token_b = _master_link(master_b, "Мастер Б")

    assert _start(client, 920000007, token_a).status_code == 200
    assert _start(client, 920000007, token_b).status_code == 200
    assert _start(client, 920000008, token_b).status_code == 200

    response = client.get("/api/v1/client/context", headers=_headers(920000007))
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "choose_master"
    assert [master["display_name"] for master in payload["masters"]] == [
        "Мастер А",
        "Мастер Б",
    ]

    other = client.get("/api/v1/client/context", headers=_headers(920000008))
    assert other.status_code == 200
    assert other.json()["state"] == "ready"
    assert other.json()["master"]["display_name"] == "Мастер Б"


def test_catalog_is_selected_by_owned_binding_not_owner_input(
    client,
    create_user,
    create_service,
):
    master_a = create_user(telegram_user_id=820000006)
    master_b = create_user(telegram_user_id=820000007)
    token_a = _master_link(master_a, "Мастер А")
    _master_link(master_b, "Мастер Б")
    create_service(master_a.id, public_name="Маникюр А")
    create_service(master_b.id, public_name="Маникюр Б")

    start = _start(client, 920000009, token_a)
    binding_id = start.json()["master"]["binding_id"]
    response = client.get(
        "/api/v1/client/catalog",
        headers=_headers(920000009, binding_id=binding_id),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["master"]["display_name"] == "Мастер А"
    assert [service["public_name"] for service in payload["services"]] == [
        "Маникюр А"
    ]


def test_binding_handle_cannot_be_used_by_another_telegram_identity(client, create_user):
    master = create_user(telegram_user_id=820000008)
    token = _master_link(master, "Мастер В")
    start = _start(client, 920000010, token)
    binding_id = start.json()["master"]["binding_id"]

    response = client.get(
        "/api/v1/client/catalog",
        headers=_headers(920000011, binding_id=binding_id),
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "client_binding_not_found"
