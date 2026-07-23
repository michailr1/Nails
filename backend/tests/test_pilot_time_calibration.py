from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import Service
from app.services.catalog_inclusions import (
    replace_included_addons,
    replace_per_unit_time_addons,
)


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


def _link_included(owner_user_id, base_name: str, addon_names: list[str]) -> None:
    with get_session_factory()() as session:
        services = session.scalars(
            select(Service).where(Service.owner_user_id == owner_user_id)
        ).all()
        by_name = {service.public_name: service for service in services}
        replace_included_addons(
            session,
            owner_user_id,
            by_name[base_name],
            [by_name[name] for name in addon_names],
        )
        session.commit()


def _mark_per_unit_time(owner_user_id, addon_names: list[str]) -> None:
    with get_session_factory()() as session:
        services = session.scalars(
            select(Service).where(Service.owner_user_id == owner_user_id)
        ).all()
        by_name = {service.public_name: service for service in services}
        replace_per_unit_time_addons(
            session,
            owner_user_id,
            [by_name[name] for name in addon_names],
        )
        session.commit()


def _book(
    client: TestClient,
    headers: dict[str, str],
    *,
    service_name: str,
    addon_names: list[str],
    idempotency_key: str,
    addon_quantities: dict[str, int] | None = None,
):
    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json={
            "client_public_name": "Анна",
            "service_name": service_name,
            "addon_names": addon_names,
            "addon_quantities": addon_quantities or {},
            "starts_at": "2026-07-24T12:00:00+02:00",
            "idempotency_key": idempotency_key,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["booking"]


@pytest.mark.usefixtures("clean_database")
def test_manicure_coating_does_not_double_count_removal_and_reinforcement(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    headers = auth_headers(request_id="manicure-included-time")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Маникюр с покрытием",
        price_amount="2700.00",
        duration_minutes=130,
        buffer_after_minutes=5,
    )
    _create_service(
        client,
        headers,
        public_name="Снятие",
        kind="addon",
        price_amount="100.00",
        extra_minutes=10,
    )
    _create_service(
        client,
        headers,
        public_name="Укрепление",
        kind="addon",
        price_type="on_request",
        extra_minutes=50,
    )
    _link_included(
        owner.id,
        "Маникюр с покрытием",
        ["Снятие", "Укрепление"],
    )

    booking = _book(
        client,
        headers,
        service_name="Маникюр с покрытием",
        addon_names=["Снятие", "Укрепление"],
        idempotency_key="manicure-no-double-count",
    )

    assert booking["duration_minutes"] == 130
    addons = {
        item["public_name"]: item
        for item in booking["catalog_items"]
        if item["kind"] == "addon"
    }
    assert addons["Снятие"]["time_included_in_base"] is True
    assert addons["Укрепление"]["time_included_in_base"] is True


@pytest.mark.usefixtures("clean_database")
def test_pedicure_coating_does_not_double_count_removal(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    headers = auth_headers(request_id="pedicure-included-time")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Педикюр с покрытием",
        price_type="on_request",
        duration_minutes=120,
        buffer_after_minutes=10,
    )
    _create_service(
        client,
        headers,
        public_name="Снятие",
        kind="addon",
        price_amount="100.00",
        extra_minutes=10,
    )
    _link_included(owner.id, "Педикюр с покрытием", ["Снятие"])

    booking = _book(
        client,
        headers,
        service_name="Педикюр с покрытием",
        addon_names=["Снятие"],
        idempotency_key="pedicure-no-double-count",
    )

    assert booking["duration_minutes"] == 120
    assert booking["price_type"] == "on_request"
    assert booking["price_amount"] is None


@pytest.mark.usefixtures("clean_database")
def test_repair_three_nails_scales_time_price_and_snapshot(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    headers = auth_headers(request_id="repair-quantity")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Маникюр с покрытием",
        price_amount="2700.00",
        duration_minutes=130,
        buffer_after_minutes=5,
    )
    _create_service(
        client,
        headers,
        public_name="Ремонт ногтя",
        kind="addon",
        price_type="per_unit",
        price_amount="300.00",
        price_unit="ноготь",
        extra_minutes=10,
    )
    _mark_per_unit_time(owner.id, ["Ремонт ногтя"])

    booking = _book(
        client,
        headers,
        service_name="Маникюр с покрытием",
        addon_names=["Ремонт ногтя"],
        addon_quantities={"Ремонт ногтя": 3},
        idempotency_key="repair-three",
    )

    assert booking["duration_minutes"] == 160
    assert booking["price_type"] == "fixed"
    assert booking["price_amount"] == "3600.00"
    repair = next(
        item
        for item in booking["catalog_items"]
        if item["public_name"] == "Ремонт ногтя"
    )
    assert repair["quantity"] == 3
    assert repair["time_included_in_base"] is False
    assert repair["time_per_unit"] is True


@pytest.mark.usefixtures("clean_database")
def test_quantity_is_part_of_idempotency_contract(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    owner = create_user()
    headers = auth_headers(request_id="quantity-idempotency")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Маникюр",
        price_amount="2000.00",
        duration_minutes=60,
    )
    _create_service(
        client,
        headers,
        public_name="Ремонт ногтя",
        kind="addon",
        price_type="per_unit",
        price_amount="300.00",
        price_unit="ноготь",
        extra_minutes=10,
    )
    _mark_per_unit_time(owner.id, ["Ремонт ногтя"])
    _book(
        client,
        headers,
        service_name="Маникюр",
        addon_names=["Ремонт ногтя"],
        addon_quantities={"Ремонт ногтя": 1},
        idempotency_key="quantity-key",
    )

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "addon_names": ["Ремонт ногтя"],
            "addon_quantities": {"Ремонт ногтя": 2},
            "starts_at": "2026-07-24T12:00:00+02:00",
            "idempotency_key": "quantity-key",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "idempotency_conflict"


@pytest.mark.usefixtures("clean_database")
def test_quantity_is_rejected_for_non_per_unit_time_addon(
    client: TestClient,
    create_user: Callable,
    auth_headers: Callable,
) -> None:
    create_user()
    headers = auth_headers(request_id="quantity-rejected")
    _create_client(client, headers)
    _create_service(
        client,
        headers,
        public_name="Маникюр",
        price_amount="2000.00",
        duration_minutes=60,
    )
    _create_service(
        client,
        headers,
        public_name="Френч",
        kind="addon",
        price_amount="500.00",
        extra_minutes=20,
    )

    response = client.post(
        "/api/v1/scheduling/bookings",
        headers=headers,
        json={
            "client_public_name": "Анна",
            "service_name": "Маникюр",
            "addon_names": ["Френч"],
            "addon_quantities": {"Френч": 2},
            "starts_at": "2026-07-24T12:00:00+02:00",
            "idempotency_key": "quantity-rejected",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "addon_quantity_not_supported"
