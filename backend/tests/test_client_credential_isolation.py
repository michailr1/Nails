from __future__ import annotations

import os


def test_client_key_is_not_accepted_by_master_api(client, create_user):
    user = create_user(telegram_user_id=930000001)
    response = client.get(
        "/api/v1/onboarding",
        headers={
            "X-Nails-Client-Internal-Key": "c" * 64,
            "X-Telegram-User-ID": str(user.telegram_user_id),
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_master_key_is_not_accepted_by_client_api(client):
    response = client.get(
        "/api/v1/client/context",
        headers={
            "X-Nails-Internal-Key": os.environ["INTERNAL_API_KEY"],
            "X-Telegram-User-ID": "930000002",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"
