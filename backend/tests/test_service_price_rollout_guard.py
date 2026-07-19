from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

NON_FIXED_PAYLOADS = [
    pytest.param(
        {
            "price_type": "range",
            "price_min_amount": "1900.00",
            "price_max_amount": "2300.00",
        },
        {
            "price_type": "range",
            "price_amount": None,
            "price_min_amount": "1900.00",
            "price_max_amount": "2300.00",
            "price_unit": None,
        },
        id="range",
    ),
    pytest.param(
        {
            "price_type": "per_unit",
            "price_amount": "100.00",
            "price_unit": "1 ноготь",
        },
        {
            "price_type": "per_unit",
            "price_amount": "100.00",
            "price_min_amount": None,
            "price_max_amount": None,
            "price_unit": "1 ноготь",
        },
        id="per-unit",
    ),
    pytest.param(
        {"price_type": "on_request"},
        {
            "price_type": "on_request",
            "price_amount": None,
            "price_min_amount": None,
            "price_max_amount": None,
            "price_unit": None,
        },
        id="on-request",
    ),
]


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize(("price_fields", "expected"), NON_FIXED_PAYLOADS)
def test_non_fixed_create_is_visible_with_full_semantics(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    price_fields: dict[str, object],
    expected: dict[str, object],
) -> None:
    create_user()

    response = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id=f"create-{price_fields['price_type']}"),
        json={
            "public_name": "Гибкая цена",
            "duration_minutes": 120,
            **price_fields,
        },
    )
    assert response.status_code == 200, response.text

    service = response.json()["service"]
    for field, value in expected.items():
        assert service[field] == value

    lookup = client.get(
        "/api/v1/scheduling/services/exact",
        headers=auth_headers(),
        params={"public_name": "Гибкая цена"},
    )
    assert lookup.status_code == 200, lookup.text
    for field, value in expected.items():
        assert lookup.json()["service"][field] == value


@pytest.mark.usefixtures("clean_database")
@pytest.mark.parametrize(("price_fields", "expected"), NON_FIXED_PAYLOADS)
def test_non_fixed_replace_changes_existing_fixed_service(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
    price_fields: dict[str, object],
    expected: dict[str, object],
) -> None:
    create_user()

    created = client.post(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="fixed-create"),
        json={
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
        },
    )
    assert created.status_code == 200, created.text

    replaced = client.put(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id=f"replace-{price_fields['price_type']}"),
        json={
            "current_public_name": "Маникюр",
            "public_name": "Маникюр",
            "currency": "RUB",
            "duration_minutes": 120,
            "buffer_before_minutes": 0,
            "buffer_after_minutes": 0,
            **price_fields,
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["changed"] is True
    assert "price_type" in replaced.json()["changed_fields"]

    service = replaced.json()["service"]
    for field, value in expected.items():
        assert service[field] == value
