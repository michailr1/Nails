from __future__ import annotations

from pathlib import Path

APP = Path(__file__).parents[1] / "app"


def test_web_booking_mutations_reuse_domain_services_and_boundary() -> None:
    source = (APP / "api" / "web_booking_mutations.py").read_text(encoding="utf-8")

    assert '@router.put("/reschedule"' in source
    assert '@router.put("/cancel"' in source
    assert '@router.put("/{booking_id}"' in source
    assert "validate_web_boundary(request)" in source
    assert "reschedule_booking(session, identity, body)" in source
    assert "cancel_booking(session, identity, body)" in source
    assert "update_booking(session, identity, booking_id, body)" in source
    assert "require_web_session_identity(session, request)" in source


def test_booking_edit_ui_refreshes_calendar_without_client_messages() -> None:
    source = (APP / "web_static" / "web-booking-edit.js").read_text(encoding="utf-8")

    assert 'booking.status === "scheduled"' in source
    assert 'booking.status === "completed"' in source
    assert 'method: "PUT"' in source
    assert "/web/api/bookings/${booking.booking_id}" in source
    assert "/web/api/bookings/cancel" in source
    assert "await renderCalendar()" in source
    assert "window.confirm" in source
    assert "client_public_name" in source
    assert "addon_names" in source
    assert "price_override_amount" in source
    assert "duration_override_minutes" in source
    assert "sendMessage" not in source
