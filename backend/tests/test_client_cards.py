from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent, Client

CLIENT_CARD = {
    "public_name": "Анна Тестовая",
    "phone": "+34 600 000 000",
    "private_alias": "Анна сложные ногти",
    "contact_channel": "Telegram",
    "birthday": "1990-05-12",
    "notes": "Предпочитает вечерние записи",
    "nail_skin_notes": "Тонкая ногтевая пластина",
    "sensitivity_notes": "Чувствительность к резким запахам",
    "style_preferences": "Короткий миндаль, молочные оттенки",
    "communication_preferences": "Писать без звонков",
}


@pytest.mark.usefixtures("clean_database")
def test_old_client_payload_remains_valid_and_new_fields_default_to_null(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    created = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="client-old-contract"),
        json={"public_name": "Анна", "phone": None},
    )

    assert created.status_code == 200, created.text
    card = created.json()["client"]
    assert card["public_name"] == "Анна"
    for field in (
        "private_alias",
        "contact_channel",
        "birthday",
        "notes",
        "nail_skin_notes",
        "sensitivity_notes",
        "style_preferences",
        "communication_preferences",
    ):
        assert card[field] is None


@pytest.mark.usefixtures("clean_database")
def test_client_card_can_be_created_read_and_replaced_owner_scoped(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user(telegram_user_id=100000001)
    create_user(telegram_user_id=100000002)

    created = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(
            telegram_user_id=100000001,
            request_id="client-card-create",
        ),
        json=CLIENT_CARD,
    )
    assert created.status_code == 200, created.text
    assert created.json()["created"] is True
    assert created.json()["client"]["private_alias"] == "Анна сложные ногти"

    exact_by_public_name = client.get(
        "/api/v1/scheduling/clients/exact",
        headers=auth_headers(telegram_user_id=100000001),
        params={"public_name": "Анна Тестовая"},
    )
    assert exact_by_public_name.status_code == 200, exact_by_public_name.text
    assert exact_by_public_name.json()["client"]["style_preferences"] == CLIENT_CARD[
        "style_preferences"
    ]

    hidden_from_other_owner = client.get(
        "/api/v1/scheduling/clients/exact",
        headers=auth_headers(telegram_user_id=100000002),
        params={"public_name": "Анна Тестовая"},
    )
    assert hidden_from_other_owner.status_code == 200, hidden_from_other_owner.text
    assert hidden_from_other_owner.json() == {"found": False, "client": None}

    replacement = {
        **CLIENT_CARD,
        "current_public_name": "Анна Тестовая",
        "phone": "+34 611 111 111",
        "private_alias": "Аня сложные ногти",
        "notes": None,
    }
    updated = client.put(
        "/api/v1/scheduling/clients",
        headers=auth_headers(
            telegram_user_id=100000001,
            request_id="client-card-update",
        ),
        json=replacement,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["changed"] is True
    assert set(body["changed_fields"]) == {"notes", "phone", "private_alias"}
    assert body["client"]["notes"] is None
    assert body["client"]["phone"] == "+34 611 111 111"


@pytest.mark.usefixtures("clean_database")
def test_private_alias_participates_in_candidates_but_never_replaces_public_name(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    created = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(),
        json=CLIENT_CARD,
    )
    assert created.status_code == 200, created.text

    candidates = client.get(
        "/api/v1/scheduling/clients/candidates",
        headers=auth_headers(),
        params={"public_name": "Анна сложные ногти"},
    )
    assert candidates.status_code == 200, candidates.text
    assert len(candidates.json()["candidates"]) == 1
    candidate = candidates.json()["candidates"][0]
    assert candidate["public_name"] == "Анна Тестовая"
    assert candidate["private_alias"] == "Анна сложные ногти"


@pytest.mark.usefixtures("clean_database")
def test_client_audit_records_changed_field_names_without_private_values(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    created = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="private-audit-create"),
        json=CLIENT_CARD,
    )
    assert created.status_code == 200, created.text

    updated = client.put(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id="private-audit-update"),
        json={
            **CLIENT_CARD,
            "current_public_name": CLIENT_CARD["public_name"],
            "sensitivity_notes": "Секретная чувствительность",
        },
    )
    assert updated.status_code == 200, updated.text

    with get_session_factory()() as session:
        stored = session.scalar(
            select(Client).where(Client.public_name == "Анна Тестовая")
        )
        assert stored is not None
        events = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.object_id == stored.id)
            .order_by(AuditEvent.created_at)
        ).all()
    serialized = " ".join(str(event.safe_changes) for event in events)
    assert "Секретная чувствительность" not in serialized
    assert "Тонкая ногтевая пластина" not in serialized
    assert "changed_fields" in serialized
