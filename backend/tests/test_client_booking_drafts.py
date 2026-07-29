from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import insert

from app.client_models import BookingRequest, MasterPublicProfile
from app.db import get_session_factory
from app.models import Service
from app.services.catalog_inclusions import service_per_unit_time_addons
from app.services.client_binding import create_master_link_token
from app.services.normalization import normalize_public_name

CLIENT_KEY = "c" * 64
BERLIN = ZoneInfo("Europe/Berlin")


def _headers(telegram_user_id: int, binding_id=None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "client-booking-draft-test",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = str(binding_id)
    return headers


def _start_binding(client, master, telegram_user_id: int, name: str = "Анна"):
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master.id, display_name="Мастер"))
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers=_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": name},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def _service(
    owner_id,
    name: str,
    *,
    kind: str,
    price: str,
    duration: int = 0,
    extra: int = 0,
    price_type: str = "fixed",
) -> Service:
    with get_session_factory()() as session:
        row = Service(
            owner_user_id=owner_id,
            public_name=name,
            normalized_public_name=normalize_public_name(name),
            price_amount=Decimal(price),
            currency="RUB",
            duration_minutes=duration,
            buffer_before_minutes=0,
            buffer_after_minutes=0,
            is_active=True,
            kind=kind,
            price_type=price_type,
            price_unit="ноготь" if price_type == "per_unit" else None,
            extra_minutes=extra,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row


def _create_draft(client, telegram_id, binding_id, service_name="Маникюр"):
    response = client.post(
        "/api/v1/client/booking-drafts",
        headers=_headers(telegram_id, binding_id),
        json={"service_name": service_name},
    )
    assert response.status_code == 200
    return response.json()


def test_draft_composition_price_duration_and_slots(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=850000001)
    _service(master.id, "Маникюр", kind="base", price="2500", duration=60)
    repair = _service(
        master.id,
        "Ремонт",
        kind="addon",
        price="300",
        extra=15,
        price_type="per_unit",
    )
    with get_session_factory()() as session:
        session.execute(
            insert(service_per_unit_time_addons).values(
                owner_user_id=master.id,
                addon_service_id=repair.id,
            )
        )
        session.commit()
    day = date.today() + timedelta(days=30)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(13))
    binding_id = _start_binding(client, master, 950000001)

    draft = _create_draft(client, 950000001, binding_id)
    assert draft["duration_minutes"] == 60
    repair_option = next(
        item for item in draft["addons"] if item["public_name"] == "Ремонт"
    )
    assert repair_option["quantity_supported"] is True
    assert repair_option["time_per_unit"] is True

    base_slots = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slots",
        headers=_headers(950000001),
        params={"day": day.isoformat()},
    )
    assert base_slots.status_code == 200
    assert len(base_slots.json()["starts_at"]) == 9

    changed = client.put(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/composition",
        headers=_headers(950000001),
        json={"addon_names": ["Ремонт"], "addon_quantities": {"ремонт": 2}},
    )
    assert changed.status_code == 200
    summary = changed.json()
    assert summary["duration_minutes"] == 90
    assert summary["price_type"] == "fixed"
    assert summary["price_amount"] == "3100.00"
    assert summary["addon_quantities"] == {"ремонт": 2}

    composition_slots = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slots",
        headers=_headers(950000001),
        params={"day": day.isoformat()},
    )
    assert composition_slots.status_code == 200
    assert len(composition_slots.json()["starts_at"]) == 7


def test_draft_submit_persists_composition_without_reserving(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=850000002)
    _service(master.id, "Маникюр", kind="base", price="2500", duration=60)
    _service(master.id, "Снятие", kind="addon", price="300", extra=30)
    day = date.today() + timedelta(days=31)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(16))
    binding_id = _start_binding(client, master, 950000002, "Анна Draft")
    draft = _create_draft(client, 950000002, binding_id)

    changed = client.put(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/composition",
        headers=_headers(950000002),
        json={"addon_names": ["Снятие"], "addon_quantities": {}},
    )
    assert changed.status_code == 200
    slots = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slots",
        headers=_headers(950000002),
        params={"day": day.isoformat()},
    ).json()["starts_at"]
    chosen = slots[0]

    selected = client.put(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slot",
        headers=_headers(950000002),
        json={"starts_at": chosen},
    )
    assert selected.status_code == 200
    submitted = client.post(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/submit",
        headers=_headers(950000002),
    )
    assert submitted.status_code == 200
    payload = submitted.json()
    assert payload["status"] == "pending"
    assert payload["addon_names"] == ["Снятие"]

    with get_session_factory()() as session:
        request = session.get(BookingRequest, payload["request_id"])
        assert request is not None
        assert request.booking_id is None
        assert request.addon_names == ["Снятие"]

    fresh = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slots",
        headers=_headers(950000002),
        params={"day": day.isoformat()},
    )
    assert chosen in fresh.json()["starts_at"]

    retried = client.post(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/submit",
        headers=_headers(950000002),
    )
    assert retried.status_code == 200
    assert retried.json()["request_id"] == payload["request_id"]


def test_composition_change_clears_selected_slot_and_stale_addon_blocks_submit(
    client,
    create_user,
    create_availability,
):
    master = create_user(telegram_user_id=850000003)
    _service(master.id, "Маникюр", kind="base", price="2500", duration=60)
    addon = _service(master.id, "Снятие", kind="addon", price="300", extra=30)
    day = date.today() + timedelta(days=32)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(16))
    binding_id = _start_binding(client, master, 950000003)
    draft = _create_draft(client, 950000003, binding_id)
    slots = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slots",
        headers=_headers(950000003),
        params={"day": day.isoformat()},
    ).json()["starts_at"]
    selected = client.put(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/slot",
        headers=_headers(950000003),
        json={"starts_at": slots[0]},
    )
    assert selected.status_code == 200
    assert selected.json()["starts_at"] is not None

    changed = client.put(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/composition",
        headers=_headers(950000003),
        json={"addon_names": ["Снятие"], "addon_quantities": {}},
    )
    assert changed.status_code == 200
    assert changed.json()["starts_at"] is None

    no_slot = client.post(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/submit",
        headers=_headers(950000003),
    )
    assert no_slot.status_code == 422
    assert no_slot.json()["detail"]["code"] == "client_booking_slot_required"

    with get_session_factory()() as session:
        stored = session.get(Service, addon.id)
        stored.is_active = False
        session.commit()
    stale = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}",
        headers=_headers(950000003),
    )
    assert stale.status_code == 404
    assert stale.json()["detail"]["code"] == "addon_not_found"


def test_draft_is_binding_scoped_and_quantity_rules_are_enforced(
    client,
    create_user,
):
    master = create_user(telegram_user_id=850000004)
    _service(master.id, "Маникюр", kind="base", price="2500", duration=60)
    _service(master.id, "Снятие", kind="addon", price="300", extra=30)
    binding_a = _start_binding(client, master, 950000004, "Анна")
    binding_b = _start_binding(client, master, 950000005, "Мария")
    draft = _create_draft(client, 950000004, binding_a)

    foreign = client.get(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}",
        headers=_headers(950000005),
    )
    assert foreign.status_code == 404

    invalid = client.put(
        f"/api/v1/client/booking-drafts/{draft['draft_id']}/composition",
        headers=_headers(950000004),
        json={"addon_names": ["Снятие"], "addon_quantities": {"снятие": 2}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "addon_quantity_not_supported"
