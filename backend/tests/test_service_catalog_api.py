from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_fixed_catalog_rows_persist_and_sort_stably(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    payloads = [
        {
            "public_name": "Сложный дизайн",
            "price_amount": "900.00",
            "duration_minutes": 30,
            "category": "Дизайн",
            "sort_order": 20,
        },
        {
            "public_name": "Педикюр",
            "price_amount": "2300.00",
            "duration_minutes": 100,
            "category": "База",
            "sort_order": 20,
        },
        {
            "public_name": "Маникюр",
            "price_amount": "2700.00",
            "duration_minutes": 120,
            "category": "База",
            "sort_order": 10,
        },
    ]

    for index, payload in enumerate(payloads, start=1):
        response = client.post(
            "/api/v1/scheduling/services",
            headers=auth_headers(request_id=f"catalog-create-{index}"),
            json=payload,
        )
        assert response.status_code == 200, response.text

    response = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(),
    )
    assert response.status_code == 200, response.text

    services = response.json()["services"]
    assert [service["public_name"] for service in services] == [
        "Маникюр",
        "Педикюр",
        "Сложный дизайн",
    ]
    assert all(service["kind"] == "base" for service in services)
    assert all(service["price_type"] == "fixed" for service in services)
    assert [service["price_amount"] for service in services] == [
        "2700.00",
        "2300.00",
        "900.00",
    ]
