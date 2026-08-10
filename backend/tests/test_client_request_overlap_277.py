from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.client_models import BookingRequest, MasterPublicProfile
from app.db import get_session_factory
from app.models import Booking, Client, Service
from app.services.client_binding import create_master_link_token
from app.services.normalization import normalize_public_name

CLIENT_KEY = "c" * 64
BERLIN = ZoneInfo("Europe/Berlin")


def _client_headers(telegram_user_id: int, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "request-overlap-277",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _start_binding(client, master, telegram_user_id: int, name: str) -> str:
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master.id, display_name="Мастер"))
        session.flush()
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": name},
    )
    assert response.status_code == 200, response.text
    return response.json()["master"]["binding_id"]


def _add_addon(owner_user_id, name: str, *, extra_minutes: int) -> None:
    with get_session_factory()() as session:
        session.add(
            Service(
                owner_user_id=owner_user_id,
                public_name=name,
                normalized_public_name=normalize_public_name(name),
                public_description=None,
                price_amount=Decimal("500.00"),
                currency="RUB",
                duration_minutes=1,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                is_active=True,
                kind="addon",
                price_type="fixed",
                category="Дополнения",
                sort_order=0,
                extra_minutes=extra_minutes,
            )
        )
        session.commit()


def _add_client(owner_user_id, name: str) -> None:
    with get_session_factory()() as session:
        session.add(
            Client(
                owner_user_id=owner_user_id,
                public_name=name,
                normalized_public_name=normalize_public_name(name),
            )
        )
        session.commit()


def test_master_added_addon_overlap_is_reported_before_request_mutation(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=870000001)
    create_service(
        master.id,
        public_name="Маникюр",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    _add_addon(master.id, "Сложный дизайн", extra_minutes=50)

    day = date.today() + timedelta(days=24)
    create_availability(master.id, day=day, start_time=time(10), end_time=time(18))

    # Existing booking starts exactly when the original 60-minute request ends.
    # The request itself therefore fits, but adding a +50 minute addon must overlap.
    _add_client(master.id, "Занятая клиентка")
    blocking_start = datetime.combine(day, time(12), tzinfo=BERLIN)
    blocking = client.post(
        "/api/v1/scheduling/bookings",
        headers=auth_headers(master.telegram_user_id, request_id="overlap-blocker-277"),
        json={
            "client_public_name": "Занятая клиентка",
            "service_name": "Маникюр",
            "addon_names": [],
            "addon_quantities": {},
            "starts_at": blocking_start.isoformat(),
            "idempotency_key": "overlap-blocker-277",
        },
    )
    assert blocking.status_code == 200, blocking.text

    binding_id = _start_binding(client, master, 970000001, "Людмила")
    requested_start = datetime.combine(day, time(11), tzinfo=BERLIN)
    created = client.post(
        "/api/v1/client/requests",
        headers=_client_headers(970000001, binding_id),
        json={
            "service_name": "Маникюр",
            "addon_names": [],
            "addon_quantities": {},
            "starts_at": requested_start.isoformat(),
            "idempotency_key": "request-overlap-277",
        },
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["id"]

    failed = client.post(
        f"/api/v1/scheduling/client-requests/{request_id}/approve",
        headers=auth_headers(master.telegram_user_id, request_id="approve-overlap-277"),
        json={
            "resolution": "create_new",
            "service_name": "Маникюр",
            "addon_names": ["Сложный дизайн"],
            "addon_quantities": {},
            "starts_at": requested_start.isoformat(),
        },
    )

    assert failed.status_code == 409, failed.text
    assert failed.json()["detail"]["code"] == "booking_overlap"

    with get_session_factory()() as session:
        request = session.get(BookingRequest, request_id)
        assert request is not None
        assert request.status == "pending"
        assert request.booking_id is None
        assert request.client_id is None
        assert request.service_name == "Маникюр"
        assert request.addon_names == []
        assert request.addon_quantities == {}
        assert request.starts_at.astimezone(BERLIN) == requested_start

        # The failed approval must not leave a newly-created client or booking behind.
        leaked_client_count = session.scalar(
            select(func.count(Client.id)).where(
                Client.owner_user_id == master.id,
                Client.normalized_public_name == normalize_public_name("Людмила"),
            )
        )
        assert leaked_client_count == 0

        bookings = session.scalars(
            select(Booking).where(Booking.owner_user_id == master.id)
        ).all()
        assert len(bookings) == 1
        assert bookings[0].starts_at.astimezone(BERLIN) == blocking_start


def test_cabinet_keeps_overlap_error_visible_and_dialog_open() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/web_static/web-client-requests.js").read_text(
        encoding="utf-8"
    )

    assert (
        'booking_overlap: "Это время уже занято другой записью. '
        'Заявка не изменилась — выберите другое время."'
    ) in source

    approval = 'await api(`/web/api/client-requests/${encodeURIComponent(request.id)}/approve`'
    error = "errorLine.textContent = clientRequestErrorText(error);"
    refresh = "await refreshRequestSlots(dialog, request);"
    close = "closeClientRequestDialog();"

    approval_index = source.index(approval)
    catch_index = source.index("} catch (error) {", approval_index)
    error_index = source.index(error, catch_index)
    refresh_index = source.index(refresh, error_index)
    next_close = source.find(close, catch_index)

    assert error_index < refresh_index
    assert next_close == -1 or next_close > refresh_index
