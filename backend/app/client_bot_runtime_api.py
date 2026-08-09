from __future__ import annotations

from typing import Any

from app.client_bot import RemoteCallError
from app.client_bot_booking_flow import DraftNailsClientApi


class ClientDomainRemoteCallError(RemoteCallError):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class RuntimeDraftNailsClientApi(DraftNailsClientApi):
    def _request(
        self,
        method: str,
        path: str,
        *,
        telegram_user_id: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        binding_id = kwargs.pop("binding_id", None)
        response = self._client.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers(telegram_user_id, binding_id),
            timeout=15.0,
            **kwargs,
        )
        if response.status_code >= 400:
            code = None
            try:
                body = response.json()
                detail = body.get("detail") if isinstance(body, dict) else None
                if isinstance(detail, dict):
                    code = str(detail.get("code") or "") or None
            except ValueError:
                pass
            raise ClientDomainRemoteCallError(
                f"client API {path} returned {response.status_code}",
                code=code,
                status_code=response.status_code,
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise ClientDomainRemoteCallError(
                f"client API {path} returned invalid JSON"
            )
        return payload

    def masters(self, telegram_user_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/client/masters",
            telegram_user_id=telegram_user_id,
        )

    def confirmed_contact(
        self,
        telegram_user_id: int,
        binding_id: str,
        *,
        contact_user_id: int,
        phone_number: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/linking/confirmed-contact",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
            json={
                "contact_user_id": contact_user_id,
                "phone_number": phone_number,
            },
        )

    def contact_forward(
        self,
        telegram_user_id: int,
        binding_id: str,
        message_text: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/contact-forward",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
            json={"message_text": message_text},
        )

    def repeat_last_preview(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        if getattr(self, "_client", None) is None:
            return {"available": False}
        try:
            return self._request(
                "GET",
                "/api/v1/client/booking-drafts/repeat-last",
                telegram_user_id=telegram_user_id,
                binding_id=binding_id,
            )
        except ClientDomainRemoteCallError:
            return {"available": False}

    def create_repeat_last_draft(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/booking-drafts/repeat-last",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
        )

    def update_draft_note(
        self,
        telegram_user_id: int,
        draft_id: str,
        note: str | None,
    ) -> dict[str, Any]:
        return self._request(
            "PUT",
            f"/api/v1/client/booking-drafts/{draft_id}/note",
            telegram_user_id=telegram_user_id,
            json={"note": note},
        )

    def booking_requests(
        self,
        telegram_user_id: int,
        binding_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/client/requests",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
        )

    def cancel_booking_request(
        self,
        telegram_user_id: int,
        binding_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/client/requests/{request_id}/cancel",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
        )
