from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from app.client_bot import (
    NailsClientApi,
    PlatformBot,
    _parse_slot,
    format_service_price,
    master_menu_keyboard,
    resolve_current_slot,
)


class DraftNailsClientApi(NailsClientApi):
    def create_draft(
        self,
        telegram_user_id: int,
        binding_id: str,
        service_name: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/client/booking-drafts",
            telegram_user_id=telegram_user_id,
            binding_id=binding_id,
            json={"service_name": service_name},
        )

    def draft(self, telegram_user_id: int, draft_id: str) -> dict[str, Any]:
        uuid.UUID(draft_id)
        return self._request(
            "GET",
            f"/api/v1/client/booking-drafts/{draft_id}",
            telegram_user_id=telegram_user_id,
        )

    def update_draft(
        self,
        telegram_user_id: int,
        draft_id: str,
        *,
        addon_names: list[str],
        addon_quantities: dict[str, int],
    ) -> dict[str, Any]:
        uuid.UUID(draft_id)
        return self._request(
            "PUT",
            f"/api/v1/client/booking-drafts/{draft_id}/composition",
            telegram_user_id=telegram_user_id,
            json={
                "addon_names": addon_names,
                "addon_quantities": addon_quantities,
            },
        )

    def draft_slots(
        self,
        telegram_user_id: int,
        draft_id: str,
        day: date,
    ) -> dict[str, Any]:
        uuid.UUID(draft_id)
        return self._request(
            "GET",
            f"/api/v1/client/booking-drafts/{draft_id}/slots",
            telegram_user_id=telegram_user_id,
            params={"day": day.isoformat()},
        )

    def select_draft_slot(
        self,
        telegram_user_id: int,
        draft_id: str,
        starts_at: str,
    ) -> dict[str, Any]:
        uuid.UUID(draft_id)
        return self._request(
            "PUT",
            f"/api/v1/client/booking-drafts/{draft_id}/slot",
            telegram_user_id=telegram_user_id,
            json={"starts_at": starts_at},
        )

    def submit_draft(
        self,
        telegram_user_id: int,
        draft_id: str,
    ) -> dict[str, Any]:
        uuid.UUID(draft_id)
        return self._request(
            "POST",
            f"/api/v1/client/booking-drafts/{draft_id}/submit",
            telegram_user_id=telegram_user_id,
        )


def draft_date_picker_keyboard(
    draft_id: str,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    uuid.UUID(draft_id)
    start = today or date.today()
    rows: list[list[dict[str, str]]] = []
    for offset in range(14):
        day = start + timedelta(days=offset)
        if offset % 4 == 0:
            rows.append([])
        rows[-1].append(
            {
                "text": day.strftime("%d.%m"),
                "callback_data": f"d:{draft_id}:{day:%Y%m%d}",
            }
        )
    return {"inline_keyboard": rows}


def _selected_quantity(draft: dict[str, Any], name: str) -> int:
    return int((draft.get("addon_quantities") or {}).get(name.casefold(), 1))


def draft_addon_keyboard(draft: dict[str, Any]) -> dict[str, Any]:
    draft_id = str(uuid.UUID(str(draft["draft_id"])))
    selected = set(draft.get("addon_names") or [])
    rows: list[list[dict[str, str]]] = []
    for index, option in enumerate((draft.get("addons") or [])[:20]):
        name = str(option.get("public_name") or "Дополнение")
        checked = name in selected
        quantity = _selected_quantity(draft, name)
        text = f"{'☑' if checked else '☐'} {name}"
        if checked and option.get("quantity_supported"):
            text += f" ×{quantity}"
        rows.append(
            [{"text": text[:48], "callback_data": f"a:{draft_id}:{index}"}]
        )
        if checked and option.get("quantity_supported"):
            rows.append(
                [
                    {"text": "−", "callback_data": f"qm:{draft_id}:{index}"},
                    {"text": str(quantity), "callback_data": f"a:{draft_id}:{index}"},
                    {"text": "+", "callback_data": f"qp:{draft_id}:{index}"},
                ]
            )
    rows.append([{"text": "Продолжить", "callback_data": f"dates:{draft_id}"}])
    binding_id = str(draft.get("master", {}).get("binding_id") or "")
    if binding_id:
        uuid.UUID(binding_id)
        rows.append([{"text": "← К процедурам", "callback_data": f"book:{binding_id}"}])
    return {"inline_keyboard": rows}


def draft_slot_picker_keyboard(
    draft_id: str,
    starts_at: list[Any],
    *,
    selected_day: date,
) -> dict[str, Any]:
    uuid.UUID(draft_id)
    rows: list[list[dict[str, str]]] = []
    for value in starts_at[:24]:
        parsed = _parse_slot(value)
        if parsed.date() != selected_day:
            continue
        callback = f"t:{draft_id}:{parsed:%Y%m%d%H%M}"
        if not rows or len(rows[-1]) >= 4:
            rows.append([])
        rows[-1].append({"text": parsed.strftime("%H:%M"), "callback_data": callback})
    rows.append([{"text": "← К датам", "callback_data": f"dates:{draft_id}"}])
    return {"inline_keyboard": rows}


def draft_summary_text(draft: dict[str, Any]) -> str:
    lines = ["Проверьте заявку", "", str(draft.get("service_name") or "Процедура")]
    quantities = draft.get("addon_quantities") or {}
    for name in draft.get("addon_names") or []:
        quantity = int(quantities.get(str(name).casefold(), 1))
        suffix = f" ×{quantity}" if quantity > 1 else ""
        lines.append(f"+ {name}{suffix}")
    starts_at = draft.get("starts_at")
    if starts_at:
        parsed = _parse_slot(starts_at)
        lines.extend(["", f"{parsed:%d.%m} в {parsed:%H:%M}"])
    lines.append(f"Около {int(draft.get('duration_minutes') or 0)} мин")
    lines.append(
        format_service_price(
            {
                "price_type": draft.get("price_type"),
                "price_amount": draft.get("price_amount"),
                "price_min_amount": draft.get("price_min_amount"),
                "price_max_amount": draft.get("price_max_amount"),
                "price_unit": draft.get("price_unit"),
                "currency": draft.get("currency"),
            }
        )
    )
    lines.extend(["", "После отправки мастер подтвердит заявку.", "Пока время не забронировано."])
    return "\n".join(lines)


def draft_summary_keyboard(draft_id: str) -> dict[str, Any]:
    uuid.UUID(draft_id)
    return {
        "inline_keyboard": [
            [{"text": "Отправить заявку", "callback_data": f"send:{draft_id}"}],
            [{"text": "Изменить время", "callback_data": f"dates:{draft_id}"}],
            [{"text": "Изменить дополнения", "callback_data": f"addons:{draft_id}"}],
        ]
    }


def _composition_values(
    draft: dict[str, Any],
    *,
    toggle_index: int | None = None,
    quantity_delta: int = 0,
) -> tuple[list[str], dict[str, int]]:
    options = draft.get("addons") or []
    selected = list(draft.get("addon_names") or [])
    quantities = dict(draft.get("addon_quantities") or {})
    if toggle_index is None:
        return selected, quantities
    if not 0 <= toggle_index < len(options):
        raise ValueError("stale addon index")
    option = options[toggle_index]
    name = str(option.get("public_name") or "")
    if quantity_delta:
        if name not in selected:
            selected.append(name)
        current = int(quantities.get(name.casefold(), 1))
        quantities[name.casefold()] = max(1, min(100, current + quantity_delta))
    elif name in selected:
        selected.remove(name)
        quantities.pop(name.casefold(), None)
    else:
        selected.append(name)
    return selected, quantities


class DraftPlatformBot(PlatformBot):
    def _draft_api(self) -> DraftNailsClientApi:
        if not isinstance(self._nails, DraftNailsClientApi):
            raise TypeError("DraftPlatformBot requires DraftNailsClientApi")
        return self._nails

    def _show_addons(self, chat_id: int, draft: dict[str, Any]) -> None:
        if not draft.get("addons"):
            self._send(
                chat_id,
                "Выберите дату:",
                draft_date_picker_keyboard(str(draft["draft_id"])),
            )
            return
        self._send(
            chat_id,
            f"{draft.get('service_name')}\nДобавить что-нибудь?",
            draft_addon_keyboard(draft),
        )

    def handle_callback(self, callback: dict[str, Any]) -> None:
        data = str(callback.get("data") or "")
        action, _, rest = data.partition(":")
        if action not in {"svc", "a", "qm", "qp", "addons", "dates", "d", "t", "send"}:
            return super().handle_callback(callback)

        callback_id = str(callback.get("id") or "")
        user = callback.get("from") or {}
        message = callback.get("message") or {}
        chat_id = int((message.get("chat") or {}).get("id") or 0)
        telegram_user_id = int(user.get("id") or 0)
        if callback_id:
            self._telegram.call("answerCallbackQuery", callback_query_id=callback_id)
        if telegram_user_id <= 0 or chat_id == 0:
            return
        api = self._draft_api()

        if action == "svc":
            binding_id, index_text = rest.rsplit(":", 1)
            binding_id = str(uuid.UUID(binding_id))
            _catalog, service = self._catalog_service(
                telegram_user_id,
                binding_id,
                int(index_text),
            )
            draft = api.create_draft(
                telegram_user_id,
                binding_id,
                str(service.get("public_name") or ""),
            )
            self._show_addons(chat_id, draft)
            return

        if action in {"a", "qm", "qp"}:
            draft_id, index_text = rest.rsplit(":", 1)
            draft_id = str(uuid.UUID(draft_id))
            draft = api.draft(telegram_user_id, draft_id)
            selected, quantities = _composition_values(
                draft,
                toggle_index=int(index_text),
                quantity_delta=-1 if action == "qm" else 1 if action == "qp" else 0,
            )
            updated = api.update_draft(
                telegram_user_id,
                draft_id,
                addon_names=selected,
                addon_quantities=quantities,
            )
            self._show_addons(chat_id, updated)
            return

        draft_id = str(uuid.UUID(rest.split(":", 1)[0]))
        if action == "addons":
            self._show_addons(chat_id, api.draft(telegram_user_id, draft_id))
            return
        if action == "dates":
            self._send(chat_id, "Выберите дату:", draft_date_picker_keyboard(draft_id))
            return
        if action == "d":
            _, compact_day = rest.split(":", 1)
            selected_day = date.fromisoformat(
                f"{compact_day[0:4]}-{compact_day[4:6]}-{compact_day[6:8]}"
            )
            slots = api.draft_slots(telegram_user_id, draft_id, selected_day)
            starts = slots.get("starts_at") or []
            if starts:
                self._send(
                    chat_id,
                    f"Свободное время на {selected_day:%d.%m}:",
                    draft_slot_picker_keyboard(
                        draft_id,
                        starts,
                        selected_day=selected_day,
                    ),
                )
            else:
                self._send(
                    chat_id,
                    f"На {selected_day:%d.%m} свободного времени нет.",
                    draft_date_picker_keyboard(draft_id),
                )
            return
        if action == "t":
            _, compact = rest.split(":", 1)
            selected_day = date.fromisoformat(
                f"{compact[0:4]}-{compact[4:6]}-{compact[6:8]}"
            )
            slots = api.draft_slots(telegram_user_id, draft_id, selected_day)
            starts_at = resolve_current_slot(slots.get("starts_at") or [], compact)
            if starts_at is None:
                self._send(
                    chat_id,
                    "Это время уже заняли. Выберите другое.",
                    draft_slot_picker_keyboard(
                        draft_id,
                        slots.get("starts_at") or [],
                        selected_day=selected_day,
                    ),
                )
                return
            draft = api.select_draft_slot(telegram_user_id, draft_id, starts_at)
            self._send(
                chat_id,
                draft_summary_text(draft),
                draft_summary_keyboard(draft_id),
            )
            return
        if action == "send":
            draft = api.draft(telegram_user_id, draft_id)
            result = api.submit_draft(telegram_user_id, draft_id)
            if result.get("status") != "pending":
                raise ValueError("unexpected booking request status")
            parsed = _parse_slot(result["starts_at"])
            self._send(
                chat_id,
                "✅ Заявка отправлена\n"
                f"{result.get('service_name')}\n"
                f"{parsed:%d.%m} в {parsed:%H:%M}\n\n"
                "Мастер подтвердит запись. Пока время не забронировано.",
                master_menu_keyboard(draft["master"]),
            )
