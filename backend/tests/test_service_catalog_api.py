from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("clean_database")
def test_catalog_price_shapes_persist_and_sort_stably(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()

    payloads = [
        {
            "public_name": "Сложный дизайн",
            "duration_minutes": 30,
            "category": "Дизайн",
            "sort_order": 20,
        },
        {
            "public_name": "Педикюр",
            "price_type": "range",
            "price_min_amount": "1900.00",
            "price_max_amount": "2300.00",
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
        {
            "public_name": "Дизайн ногтя",
            "kind": "addon",
            "price_type": "per_unit",
            "price_amount": "100.00",
            "price_unit": "1 ноготь",
            "extra_minutes": 10,
            "category": "Дизайн",
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
        "Дизайн ногтя",
        "Сложный дизайн",
    ]

    manicure, pedicure, nail_design, complex_design = services

    assert manicure["kind"] == "base"
    assert manicure["price_type"] == "fixed"
    assert manicure["price_amount"] == "2700.00"
    assert manicure["duration_minutes"] == 120

    assert pedicure["price_type"] == "range"
    assert pedicure["price_amount"] is None
    assert pedicure["price_min_amount"] == "1900.00"
    assert pedicure["price_max_amount"] == "2300.00"

    assert nail_design["kind"] == "addon"
    assert nail_design["price_type"] == "per_unit"
    assert nail_design["price_amount"] == "100.00"
    assert nail_design["price_unit"] == "1 ноготь"
    assert nail_design["duration_minutes"] is None
    assert nail_design["extra_minutes"] == 10

    assert complex_design["price_type"] == "on_request"
    assert complex_design["price_amount"] is None
    assert complex_design["price_min_amount"] is None
    assert complex_design["price_max_amount"] is None
