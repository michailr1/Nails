from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any, Literal

from app.client_bot import format_service_price

PAGE_SIZE = 6
CatalogMode = Literal["book", "price"]

_CATEGORY_PRIORITY = {
    "маникюр": 10,
    "педикюр": 20,
    "дизайн": 30,
    "парафинотерапия": 40,
    "дополнительно": 100,
    "другое": 110,
}


def _binding_id(payload: dict[str, Any]) -> str:
    value = str((payload.get("master") or {}).get("binding_id") or "")
    uuid.UUID(value)
    return value


def catalog_items(
    payload: dict[str, Any],
    *,
    mode: CatalogMode,
) -> list[dict[str, Any]]:
    services = list(payload.get("services") or [])
    if mode == "book":
        return [service for service in services if service.get("kind") == "base"]
    return services


def _raw_category(service: dict[str, Any]) -> str:
    return str(service.get("category") or "").strip() or "Другое"


def client_category_label(category: str, *, mode: CatalogMode) -> str:
    if category.casefold() == "дополнительно":
        if mode == "book":
            return "Снятие и другие услуги"
        return "Дополнительные услуги"
    return category


def catalog_categories(
    payload: dict[str, Any],
    *,
    mode: CatalogMode,
) -> list[str]:
    result: list[str] = []
    for service in catalog_items(payload, mode=mode):
        category = _raw_category(service)
        if category not in result:
            result.append(category)
    original_order = {category: index for index, category in enumerate(result)}
    return sorted(
        result,
        key=lambda category: (
            _CATEGORY_PRIORITY.get(category.casefold(), 50),
            original_order[category],
        ),
    )


def category_items(
    payload: dict[str, Any],
    category: str,
    *,
    mode: CatalogMode,
) -> list[tuple[int, dict[str, Any]]]:
    indexed = list(enumerate(catalog_items(payload, mode=mode)))
    return [
        (index, service)
        for index, service in indexed
        if _raw_category(service) == category
    ]


def short_service_name(service: dict[str, Any], category: str) -> str:
    name = " ".join(str(service.get("public_name") or "Услуга").split())
    folded_name = name.casefold()
    folded_category = category.casefold()
    if folded_name.startswith(folded_category):
        shortened = name[len(category) :].lstrip(" —–-:,.·")
        if shortened:
            name = shortened[:1].upper() + shortened[1:]
    return name[:48]


def format_duration(service: dict[str, Any]) -> str:
    minutes = service.get("duration_minutes")
    if minutes is None:
        return "время уточняется"
    total = max(0, int(minutes))
    hours, remainder = divmod(total, 60)
    if hours and remainder:
        return f"~{hours} ч {remainder} мин"
    if hours:
        return f"~{hours} ч"
    return f"~{remainder} мин"


def service_line(service: dict[str, Any], category: str) -> str:
    return (
        f"{short_service_name(service, category)} — "
        f"{format_service_price(service)}, {format_duration(service)}"
    )


def category_picker_keyboard(
    payload: dict[str, Any],
    *,
    mode: CatalogMode,
) -> dict[str, Any]:
    binding_id = _binding_id(payload)
    action = "cat" if mode == "book" else "pcat"
    rows = [
        [
            {
                "text": client_category_label(category, mode=mode)[:48],
                "callback_data": f"{action}:{binding_id}:{index}:0",
            }
        ]
        for index, category in enumerate(catalog_categories(payload, mode=mode))
    ]
    if mode == "book":
        rows.append(
            [
                {
                    "text": "Не знаю, подскажите",
                    "callback_data": f"help:{binding_id}",
                }
            ]
        )
    rows.append([{"text": "← Назад", "callback_data": f"master:{binding_id}"}])
    return {"inline_keyboard": rows}


def _page_slice(items: list[Any], page: int) -> tuple[int, int, list[Any]]:
    safe_page = max(0, page)
    start = safe_page * PAGE_SIZE
    return safe_page, start, items[start : start + PAGE_SIZE]


def category_page(
    payload: dict[str, Any],
    *,
    category_index: int,
    page: int,
    mode: CatalogMode,
) -> tuple[str, dict[str, Any]]:
    binding_id = _binding_id(payload)
    categories = catalog_categories(payload, mode=mode)
    if not 0 <= category_index < len(categories):
        raise ValueError("stale category index")
    category = categories[category_index]
    items = category_items(payload, category, mode=mode)
    safe_page, start, current = _page_slice(items, page)
    if not current:
        raise ValueError("stale category page")

    lines = [client_category_label(category, mode=mode), ""]
    for number, (_, service) in enumerate(current, start=1):
        lines.append(f"{number}. {service_line(service, category)}")
    if mode == "book":
        lines.extend(["", "Выберите подходящий вариант:"])

    rows: list[list[dict[str, str]]] = []
    if mode == "book":
        for number, (global_index, service) in enumerate(current, start=1):
            rows.append(
                [
                    {
                        "text": f"{number}. {short_service_name(service, category)}"[:48],
                        "callback_data": f"svc:{binding_id}:{global_index}",
                    }
                ]
            )
        rows.append(
            [
                {
                    "text": "Не знаю, подскажите",
                    "callback_data": f"help:{binding_id}",
                }
            ]
        )

    nav: list[dict[str, str]] = []
    action = "cat" if mode == "book" else "pcat"
    if safe_page > 0:
        nav.append(
            {
                "text": "← Ещё",
                "callback_data": f"{action}:{binding_id}:{category_index}:{safe_page - 1}",
            }
        )
    if start + PAGE_SIZE < len(items):
        nav.append(
            {
                "text": "Ещё →",
                "callback_data": f"{action}:{binding_id}:{category_index}:{safe_page + 1}",
            }
        )
    if nav:
        rows.append(nav)
    back_action = "book" if mode == "book" else "price"
    rows.append(
        [
            {
                "text": "← К разделам",
                "callback_data": f"{back_action}:{binding_id}",
            }
        ]
    )
    return "\n".join(lines), {"inline_keyboard": rows}


def parse_category_callback(rest: str) -> tuple[str, int, int]:
    binding_id, category_text, page_text = rest.rsplit(":", 2)
    return str(uuid.UUID(binding_id)), int(category_text), int(page_text)


def callbacks(keyboard: dict[str, Any]) -> Iterable[str]:
    for row in keyboard.get("inline_keyboard") or []:
        for button in row:
            callback = button.get("callback_data")
            if callback:
                yield str(callback)
