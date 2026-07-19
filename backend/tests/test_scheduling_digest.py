from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


def _create_booking(
    client: TestClient,
    auth_headers: Callable,
    *,
    client_name: str,
    starts_at: str,
    request_suffix: str,
) -> dict:
    created_client = client.post(
        "/api/v1/scheduling/clients",
        headers=auth_headers(request_id=f"digest-client-{request_suffix}"),
        json={"public_name": client_name, "phone": None},
    )
    assert created_client.status_code == 200, created_client.text
    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(request_id=f"digest-booking-{request_suffix}"),
        json={
            "client_public_name": client_name,
            "service_name": "Маникюр",
            "starts_at": starts_at,
            "idempotency_key": f"digest-{request_suffix}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["booking"]


def _claim(
    client: TestClient,
    headers: dict[str, str],
    *,
    local_day: str = "2026-07-19",
    now: str = "2026-07-19T21:30:00+03:00",
):
    return client.post(
        "/api/v1/scheduling/finalization-digest/claim",
        headers=headers,
        json={"local_day": local_day, "now": now},
    )


@pytest.mark.usefixtures("clean_database")
def test_digest_claim_selects_only_ended_scheduled_owner_bookings_once(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    first = create_user(telegram_user_id=1001)
    second = create_user(telegram_user_id=2002)
    create_service(first.id, price_amount="2700.00")
    create_service(second.id, price_amount="2800.00")

    def first_headers(**kwargs):
        return auth_headers(telegram_user_id=1001, **kwargs)

    def second_headers(**kwargs):
        return auth_headers(telegram_user_id=2002, **kwargs)

    _create_booking(
        client,
        first_headers,
        client_name="Анна",
        starts_at="2026-07-17T11:00:00+03:00",
        request_suffix="ended",
    )
    _create_booking(
        client,
        first_headers,
        client_name="Будущая",
        starts_at="2099-07-17T11:00:00+03:00",
        request_suffix="future",
    )
    _create_booking(
        client,
        first_headers,
        client_name="Отменённая",
        starts_at="2026-07-17T15:00:00+03:00",
        request_suffix="cancelled",
    )
    cancelled = client.put(
        "/api/v1/scheduling/bookings/cancel",
        headers=first_headers(request_id="digest-cancel"),
        json={
            "client_public_name": "Отменённая",
            "service_name": "Маникюр",
            "starts_at": "2026-07-17T15:00:00+03:00",
        },
    )
    assert cancelled.status_code == 200, cancelled.text

    _create_booking(
        client,
        first_headers,
        client_name="Закрытая",
        starts_at="2026-07-17T18:00:00+03:00",
        request_suffix="completed",
    )
    finalized = client.put(
        "/api/v1/scheduling/bookings/finalize",
        headers=first_headers(request_id="digest-finalize"),
        json={
            "client_public_name": "Закрытая",
            "service_name": "Маникюр",
            "starts_at": "2026-07-17T18:00:00+03:00",
            "outcome": "completed",
            "price_amount": None,
        },
    )
    assert finalized.status_code == 200, finalized.text

    _create_booking(
        client,
        second_headers,
        client_name="Чужая",
        starts_at="2026-07-17T12:00:00+03:00",
        request_suffix="other-owner",
    )

    claimed = _claim(
        client,
        first_headers(request_id="digest-claim-first"),
    )
    assert claimed.status_code == 200, claimed.text
    payload = claimed.json()
    assert payload["claimed"] is True
    assert payload["claim_id"]
    assert [item["client_public_name"] for item in payload["bookings"]] == ["Анна"]
    assert payload["bookings"][0]["price_amount"] == "2700.00"
    assert payload["bookings"][0]["price_type"] == "fixed"

    repeated = _claim(
        client,
        first_headers(request_id="digest-claim-repeat"),
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == {
        "claimed": False,
        "claim_id": None,
        "local_day": "2026-07-19",
        "bookings": [],
    }

    other_owner = _claim(
        client,
        second_headers(request_id="digest-claim-other"),
    )
    assert other_owner.status_code == 200, other_owner.text
    assert [
        item["client_public_name"] for item in other_owner.json()["bookings"]
    ] == ["Чужая"]


@pytest.mark.usefixtures("clean_database")
def test_digest_ack_sent_is_idempotent_and_prevents_future_prompt(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    create_service(owner.id, price_amount="2700.00")
    _create_booking(
        client,
        auth_headers,
        client_name="Анна",
        starts_at="2026-07-17T11:00:00+03:00",
        request_suffix="ack-sent",
    )
    claim = _claim(client, auth_headers(request_id="digest-claim-sent"))
    claim_id = claim.json()["claim_id"]

    ack = client.post(
        "/api/v1/scheduling/finalization-digest/ack",
        headers=auth_headers(request_id="digest-ack-sent"),
        json={"claim_id": claim_id, "sent": True},
    )
    assert ack.status_code == 200, ack.text
    assert ack.json() == {"changed": True, "sent": True, "bookings_count": 1}

    repeated = client.post(
        "/api/v1/scheduling/finalization-digest/ack",
        headers=auth_headers(request_id="digest-ack-sent-repeat"),
        json={"claim_id": claim_id, "sent": True},
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == {
        "changed": False,
        "sent": True,
        "bookings_count": 1,
    }

    next_day = _claim(
        client,
        auth_headers(request_id="digest-next-day"),
        local_day="2026-07-20",
        now="2026-07-20T21:30:00+03:00",
    )
    assert next_day.status_code == 200, next_day.text
    assert next_day.json()["claimed"] is False


@pytest.mark.usefixtures("clean_database")
def test_known_send_failure_releases_claim_for_same_day_retry(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    create_service(owner.id, price_amount="2700.00")
    _create_booking(
        client,
        auth_headers,
        client_name="Анна",
        starts_at="2026-07-17T11:00:00+03:00",
        request_suffix="release",
    )
    first = _claim(client, auth_headers(request_id="digest-claim-release"))
    first_claim_id = first.json()["claim_id"]

    released = client.post(
        "/api/v1/scheduling/finalization-digest/ack",
        headers=auth_headers(request_id="digest-release"),
        json={"claim_id": first_claim_id, "sent": False},
    )
    assert released.status_code == 200, released.text
    assert released.json() == {
        "changed": True,
        "sent": False,
        "bookings_count": 1,
    }

    retried = _claim(client, auth_headers(request_id="digest-claim-retry"))
    assert retried.status_code == 200, retried.text
    assert retried.json()["claimed"] is True
    assert retried.json()["claim_id"] != first_claim_id
