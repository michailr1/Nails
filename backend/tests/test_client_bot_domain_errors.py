from __future__ import annotations

import httpx

from app.client_bot_runtime_api import (
    ClientDomainRemoteCallError,
    RuntimeDraftNailsClientApi,
)
from app.client_bot_v1 import client_error_message


def test_client_api_preserves_domain_error_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            request=request,
            json={"detail": {"code": "client_booking_draft_expired"}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = RuntimeDraftNailsClientApi(
            client,
            base_url="http://nails.test",
            api_key="c" * 64,
        )
        try:
            api.context(900000001)
        except ClientDomainRemoteCallError as exc:
            assert exc.status_code == 409
            assert exc.code == "client_booking_draft_expired"
        else:
            raise AssertionError("domain error must be raised")


def test_known_e2e_errors_have_friendly_messages():
    codes = {
        "client_booking_draft_expired": "устарела",
        "client_identity_revoked": "больше не активна",
        "client_booking_slot_stale": "уже заняли",
        "client_pending_request_limit": "несколько заявок",
        "client_booking_draft_submitted": "уже отправлена",
    }
    for code, phrase in codes.items():
        message = client_error_message(
            ClientDomainRemoteCallError("x", code=code, status_code=409)
        )
        assert phrase in message
        assert "500" not in message


def test_unknown_domain_error_has_safe_fallback():
    message = client_error_message(
        ClientDomainRemoteCallError(
            "internal detail must not leak",
            code="unexpected",
            status_code=500,
        )
    )
    assert "internal detail" not in message
    assert "/menu" in message
