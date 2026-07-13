from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


def _services_section(body: dict) -> dict:
    return next(item for item in body["sections"] if item["section"] == "services")


@pytest.mark.usefixtures("clean_database")
def test_service_currency_defaults_to_rub_when_omitted(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()

    started = client.post("/api/v1/onboarding/start", headers=headers)
    assert started.status_code == 200

    saved = client.put(
        "/api/v1/onboarding/sections/services",
        headers=headers,
        json={
            "payload": {
                "services": [
                    {
                        "public_name": "Маникюр",
                        "price_amount": "2500.00",
                        "duration_minutes": 120,
                    }
                ]
            }
        },
    )

    assert saved.status_code == 200, saved.text
    service = _services_section(saved.json())["draft_payload"]["services"][0]
    assert service["currency"] == "RUB"
    assert service["price_amount"] == "2500.00"


@pytest.mark.usefixtures("clean_database")
def test_explicit_non_ruble_currency_is_preserved(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers()
    client.post("/api/v1/onboarding/start", headers=headers)

    saved = client.put(
        "/api/v1/onboarding/sections/services",
        headers=headers,
        json={
            "payload": {
                "services": [
                    {
                        "public_name": "Маникюр",
                        "price_amount": "50.00",
                        "currency": "EUR",
                        "duration_minutes": 120,
                    }
                ]
            }
        },
    )

    assert saved.status_code == 200, saved.text
    service = _services_section(saved.json())["draft_payload"]["services"][0]
    assert service["currency"] == "EUR"
