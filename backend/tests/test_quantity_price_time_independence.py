from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import Service
from app.services.catalog_inclusions import replace_per_unit_time_addons


def _create_client(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/scheduling/clients",
        headers=headers,
        json={"public_name": "Анна"},
    )
    assert response.status_code == 200, response.text


def _create_service(
    client: TestClient,
    headers: dict[str, str],
    **payload,
) -> None:
    response = client.post(
        "/api/v1/scheduling/services",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200, response.text


def _mark_per_unit_time(owner_user_id, addon_name: str) -> None:
    with get_session_factory()() as session:
        addon = session.scalar(
            select(Service).where(
                Service.owner_user_id == owner_user_id,
                Service.public_name == addon_name,
            )
        )
        assert addon is not None
        replace_per_unit_time_addons(session, owner_user_id, [addon])
        session.commit()


def _book(
    client: TestClient,
    headers: dict[str, str],
    *,
    addon_name: str,
    quantity: int,
    idempotency_key: str,
):
    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр с гель-лаком",
            "addon_names": [addon_name],
            "addon_quantities": {addon_name: quantity},
            "starts_at": "2026-07-24T12:00:00+02:00",
            "idempotency_key": idempotency_key,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["booking"]


@pytest.mark.usefixtures("clean_database")
def test_per_unit_design_scales_price_but_adds_time_once(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="design-quantity")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Маникюр с гель-лаком",
        price_amount="2100.00",
        duration_minutes=130,
        buffer_after_minutes=5,
    )
    _create_service(
        client,
        headers,
        public_name="Простой дизайн",
        kind="addon",
        price_type="per_unit",
        price_amount="50.00",
        price_unit="ноготь",
        extra_minutes=10,
    )

    booking = _book(
        client,
        headers,
        addon_name="Простой дизайн",
        quantity=3,
        idempotency_key="design-three",
    )

    assert booking["duration_minutes"] == 140
    assert booking["price_amount"] == "2250.00"
    design = next(
        item
        for item in booking["catalog_items"]
        if item["public_name"] == "Простой дизайн"
    )
    assert design["quantity"] == 3
    assert design["time_per_unit"] is False


@pytest.mark.usefixtures("clean_database")
def test_repair_scales_both_price_and_time_per_unit(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    headers = auth_headers(request_id="repair-corner-quantity")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Маникюр с гель-лаком",
        price_amount="2100.00",
        duration_minutes=130,
        buffer_after_minutes=5,
    )
    _create_service(
        client,
        headers,
        public_name="Ремонт или поднятие одного уголка",
        kind="addon",
        price_type="per_unit",
        price_amount="50.00",
        price_unit="уголок",
        extra_minutes=10,
    )
    _mark_per_unit_time(owner.id, "Ремонт или поднятие одного уголка")

    booking = _book(
        client,
        headers,
        addon_name="Ремонт или поднятие одного уголка",
        quantity=3,
        idempotency_key="repair-three-corners",
    )

    assert booking["duration_minutes"] == 160
    assert booking["price_amount"] == "2250.00"
    repair = next(
        item
        for item in booking["catalog_items"]
        if item["public_name"] == "Ремонт или поднятие одного уголка"
    )
    assert repair["quantity"] == 3
    assert repair["time_per_unit"] is True
