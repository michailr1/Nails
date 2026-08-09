from __future__ import annotations

from datetime import date, time, timedelta
from pathlib import Path

from sqlalchemy import select

from app.client_models import BookingRequest, ClientContactForward, MasterPublicProfile
from app.db import get_session_factory
from app.models import AuditEvent, User
from app.services.client_binding import create_master_link_token

CLIENT_KEY = "c" * 64
NOTE = "<b>Без дизайна</b>\nhttps://example.com/photo"


def _client_headers(telegram_user_id: int, binding_id: str | None = None) -> dict[str, str]:
    headers = {
        "X-Nails-Client-Internal-Key": CLIENT_KEY,
        "X-Telegram-User-ID": str(telegram_user_id),
        "X-Request-ID": "request-note-277",
    }
    if binding_id is not None:
        headers["X-Client-Binding-ID"] = binding_id
    return headers


def _start_binding(client, master, telegram_user_id: int) -> str:
    with get_session_factory()() as session:
        session.add(MasterPublicProfile(owner_user_id=master.id, display_name="Настя"))
        session.flush()
        token = create_master_link_token(session, owner_user_id=master.id).token
        session.commit()
    response = client.post(
        "/api/v1/client/start",
        headers=_client_headers(telegram_user_id),
        json={"start_token": token, "requested_public_name": "Алёна"},
    )
    assert response.status_code == 200
    return response.json()["master"]["binding_id"]


def test_request_note_is_optional_private_and_non_domain(
    client,
    create_user,
    create_service,
    create_availability,
    auth_headers,
):
    master = create_user(telegram_user_id=860000001)
    with get_session_factory()() as session:
        stored_master = session.get(User, master.id)
        assert stored_master is not None
        stored_master.timezone = "Europe/Moscow"
        session.commit()

    create_service(master.id, public_name="Маникюр", duration_minutes=60)
    day = date.today() + timedelta(days=20)
    create_availability(master.id, day=day, start_time=time(11), end_time=time(18))
    binding_id = _start_binding(client, master, 960000001)

    created = client.post(
        "/api/v1/client/booking-drafts",
        headers=_client_headers(960000001, binding_id),
        json={"service_name": "Маникюр"},
    )
    assert created.status_code == 200, created.text
    draft_before = created.json()
    draft_id = draft_before["draft_id"]
    assert draft_before["note"] is None

    too_long = client.put(
        f"/api/v1/client/booking-drafts/{draft_id}/note",
        headers=_client_headers(960000001),
        json={"note": "x" * 301},
    )
    assert too_long.status_code == 422

    noted = client.put(
        f"/api/v1/client/booking-drafts/{draft_id}/note",
        headers=_client_headers(960000001),
        json={"note": NOTE},
    )
    assert noted.status_code == 200, noted.text
    draft_after = noted.json()
    assert draft_after["note"] == NOTE
    assert draft_after["service_name"] == draft_before["service_name"]
    assert draft_after["addon_names"] == draft_before["addon_names"]
    assert draft_after["addon_quantities"] == draft_before["addon_quantities"]
    assert draft_after["duration_minutes"] == draft_before["duration_minutes"]
    assert draft_after["price_type"] == draft_before["price_type"]
    assert draft_after["price_amount"] == draft_before["price_amount"]

    slots = client.get(
        f"/api/v1/client/booking-drafts/{draft_id}/slots",
        headers=_client_headers(960000001),
        params={"day": day.isoformat()},
    )
    assert slots.status_code == 200, slots.text
    starts_at = slots.json()["starts_at"][0]

    selected = client.put(
        f"/api/v1/client/booking-drafts/{draft_id}/slot",
        headers=_client_headers(960000001),
        json={"starts_at": starts_at},
    )
    assert selected.status_code == 200, selected.text
    selected_json = selected.json()
    assert selected_json["note"] == NOTE
    selected_starts_at = selected_json["starts_at"]
    assert selected_starts_at is not None

    # Note updates are informational only. In particular they must preserve an
    # already selected slot, including blank -> null normalization and restore.
    blanked = client.put(
        f"/api/v1/client/booking-drafts/{draft_id}/note",
        headers=_client_headers(960000001),
        json={"note": "   "},
    )
    assert blanked.status_code == 200, blanked.text
    assert blanked.json()["note"] is None
    assert blanked.json()["starts_at"] == selected_starts_at

    restored = client.put(
        f"/api/v1/client/booking-drafts/{draft_id}/note",
        headers=_client_headers(960000001),
        json={"note": NOTE},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["note"] == NOTE
    assert restored.json()["starts_at"] == selected_starts_at

    too_long_after_slot = client.put(
        f"/api/v1/client/booking-drafts/{draft_id}/note",
        headers=_client_headers(960000001),
        json={"note": "x" * 301},
    )
    assert too_long_after_slot.status_code == 422
    reread = client.get(
        f"/api/v1/client/booking-drafts/{draft_id}",
        headers=_client_headers(960000001),
    )
    assert reread.status_code == 200, reread.text
    assert reread.json()["note"] == NOTE
    assert reread.json()["starts_at"] == selected_starts_at

    submitted = client.post(
        f"/api/v1/client/booking-drafts/{draft_id}/submit",
        headers=_client_headers(960000001),
    )
    assert submitted.status_code == 200, submitted.text
    client_submit = submitted.json()
    assert "note" not in client_submit
    request_id = client_submit["request_id"]

    client_list = client.get(
        "/api/v1/client/requests",
        headers=_client_headers(960000001, binding_id),
    )
    assert client_list.status_code == 200
    client_row = next(item for item in client_list.json()["requests"] if item["id"] == request_id)
    assert "note" not in client_row

    master_list = client.get(
        "/api/v1/scheduling/client-requests",
        headers=auth_headers(master.telegram_user_id),
        params={"status": "pending"},
    )
    assert master_list.status_code == 200, master_list.text
    master_row = next(item for item in master_list.json()["requests"] if item["id"] == request_id)
    assert master_row["note"] == NOTE
    assert master_row["service_name"] == client_submit["service_name"]
    assert master_row["starts_at"] == client_submit["starts_at"]

    with get_session_factory()() as session:
        request = session.get(BookingRequest, request_id)
        assert request is not None
        assert request.note == NOTE
        assert request.service_name == "Маникюр"
        assert request.addon_names == []

        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.object_id == request.id,
                AuditEvent.action == "client_booking_request.created",
            )
        )
        assert audit is not None
        serialized_audit = str(audit.safe_changes)
        assert "note" not in serialized_audit.casefold()
        assert NOTE not in serialized_audit

        forward = session.scalar(
            select(ClientContactForward).where(
                ClientContactForward.dedupe_key == f"booking-request:{request.id}"
            )
        )
        assert forward is not None
        assert forward.kind == "booking_request_created"
        assert f"Заметка клиентки: {NOTE}" in forward.message_text


def test_note_rendering_surfaces_are_plain_text_and_escaped_in_web() -> None:
    root = Path(__file__).resolve().parents[2]
    sender = (root / "ops/client_forward/send.py").read_text(encoding="utf-8")
    assert '"disable_web_page_preview": True' in sender
    assert '"parse_mode"' not in sender

    web = (root / "backend/app/web_static/web-client-requests.js").read_text(
        encoding="utf-8"
    )
    assert "escapeHtml(request.note)" in web
    assert "Заметка клиентки" in web


def test_note_schema_normalizes_blank_and_limits_length() -> None:
    from app.schemas.client_booking_drafts import ClientBookingDraftNoteUpdate

    assert ClientBookingDraftNoteUpdate(note="   ").note is None
    assert ClientBookingDraftNoteUpdate(note="  текст  ").note == "текст"
