from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient


def _item(
    name: str,
    *,
    kind: str = "base",
    price_type: str = "fixed",
    price_amount: int | None = 2500,
    duration_minutes: int | None = 120,
    extra_minutes: int = 0,
    category: str = "Маникюр",
    sort_order: int = 0,
) -> dict:
    return {
        "public_name": name,
        "public_description": None,
        "price_amount": price_amount,
        "currency": "RUB",
        "duration_minutes": duration_minutes,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "is_active": True,
        "kind": kind,
        "price_type": price_type,
        "price_min_amount": None,
        "price_max_amount": None,
        "price_unit": None,
        "category": category,
        "sort_order": sort_order,
        "extra_minutes": extra_minutes,
    }


def _replace(client: TestClient, headers: dict[str, str], services: list[dict]):
    return client.put(
        "/api/v1/scheduling/services/catalog",
        headers=headers,
        json={"services": services},
    )


@pytest.mark.usefixtures("clean_database")
def test_replace_catalog_creates_updates_archives_and_is_idempotent(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    create_service(owner.id, public_name="Старое", price_amount="1000.00")
    create_service(owner.id, public_name="Маникюр", price_amount="2000.00")

    desired = [
        _item("Маникюр", price_amount=2700, sort_order=10),
        _item(
            "Снятие",
            kind="addon",
            price_amount=300,
            duration_minutes=None,
            extra_minutes=15,
            category="Дополнительно",
            sort_order=20,
        ),
    ]
    first = _replace(
        client,
        auth_headers(request_id="catalog-replace-first"),
        desired,
    )
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["changed"] is True
    assert payload["created_count"] == 1
    assert payload["updated_count"] == 1
    assert payload["archived_count"] == 1
    assert [service["public_name"] for service in payload["services"]] == [
        "Снятие",
        "Маникюр",
    ]

    listed = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="catalog-list-all"),
        params={"include_inactive": True},
    )
    assert listed.status_code == 200, listed.text
    by_name = {service["public_name"]: service for service in listed.json()["services"]}
    assert by_name["Старое"]["is_active"] is False
    assert by_name["Маникюр"]["price_amount"] == "2700.00"
    assert by_name["Снятие"]["kind"] == "addon"

    repeated = _replace(
        client,
        auth_headers(request_id="catalog-replace-repeat"),
        desired,
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["changed"] is False
    assert repeated.json()["created_count"] == 0
    assert repeated.json()["updated_count"] == 0
    assert repeated.json()["archived_count"] == 0


@pytest.mark.usefixtures("clean_database")
def test_invalid_catalog_batch_changes_nothing(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    create_service(owner.id, public_name="Маникюр", price_amount="2500.00")

    invalid = [
        _item("Педикюр", price_amount=2800),
        _item(
            "Некорректный доп",
            kind="addon",
            price_amount=100,
            duration_minutes=30,
            extra_minutes=10,
        ),
    ]
    response = _replace(
        client,
        auth_headers(request_id="catalog-invalid"),
        invalid,
    )
    assert response.status_code == 422

    listed = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(request_id="catalog-after-invalid"),
        params={"include_inactive": True},
    )
    assert listed.status_code == 200, listed.text
    assert [service["public_name"] for service in listed.json()["services"]] == [
        "Маникюр"
    ]
    assert listed.json()["services"][0]["is_active"] is True


@pytest.mark.usefixtures("clean_database")
def test_replace_catalog_is_owner_scoped(
    client: TestClient,
    create_user: Callable,
    create_service: Callable,
    auth_headers: Callable,
) -> None:
    first = create_user(telegram_user_id=1001)
    second = create_user(telegram_user_id=2002)
    create_service(first.id, public_name="Первый", price_amount="1000.00")
    create_service(second.id, public_name="Второй", price_amount="2000.00")

    response = _replace(
        client,
        auth_headers(telegram_user_id=1001, request_id="catalog-owner"),
        [_item("Новый", price_amount=3000)],
    )
    assert response.status_code == 200, response.text

    second_list = client.get(
        "/api/v1/scheduling/services",
        headers=auth_headers(telegram_user_id=2002, request_id="catalog-other-owner"),
        params={"include_inactive": True},
    )
    assert second_list.status_code == 200, second_list.text
    assert [
        service["public_name"] for service in second_list.json()["services"]
    ] == ["Второй"]
