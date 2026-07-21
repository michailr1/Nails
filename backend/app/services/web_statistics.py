from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.models import Booking, BookingStatus, Client, Service
from app.schemas.web_statistics import (
    WebStatisticsCatalogItem,
    WebStatisticsClient,
    WebStatisticsDay,
    WebStatisticsResponse,
    WebStatisticsSummary,
)

_MAX_STATISTICS_DAYS = 366
_ZERO = Decimal("0.00")
_MONEY_STEP = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_STEP, rounding=ROUND_HALF_UP)


def _statistics_window(
    date_from: date,
    date_to: date,
) -> tuple[datetime, datetime, str, ZoneInfo]:
    if date_to < date_from:
        raise ValueError("date_to_before_date_from")
    if (date_to - date_from).days + 1 > _MAX_STATISTICS_DAYS:
        raise ValueError("date_range_too_large")
    timezone_name = get_settings().app_timezone
    timezone = ZoneInfo(timezone_name)
    local_start = datetime.combine(date_from, time.min, timezone)
    local_end = datetime.combine(date_to + timedelta(days=1), time.min, timezone)
    return local_start.astimezone(UTC), local_end.astimezone(UTC), timezone_name, timezone


def _known_amount(booking: Booking) -> Decimal | None:
    if booking.price_source == "final_price_unknown":
        return None
    return _money(booking.price_amount)


def _catalog_items(booking: Booking, service: Service) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for raw_item in booking.catalog_items_snapshot or []:
        if not isinstance(raw_item, dict):
            continue
        name = raw_item.get("public_name")
        kind = raw_item.get("kind")
        if not isinstance(name, str) or not name.strip():
            continue
        if kind not in {"base", "addon"}:
            continue
        items.append((name.strip(), kind))
    if not any(kind == "base" for _, kind in items):
        items.insert(0, (service.public_name, "base"))
    return items


def get_statistics(
    session: Session,
    identity: RequestIdentity,
    *,
    date_from: date,
    date_to: date,
    now: datetime | None = None,
) -> WebStatisticsResponse:
    starts_at, ends_at, timezone_name, timezone = _statistics_window(date_from, date_to)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)

    rows = session.execute(
        select(Booking, Client, Service)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Client.owner_user_id == identity.user_id,
            Service.owner_user_id == identity.user_id,
            Booking.starts_at >= starts_at,
            Booking.starts_at < ends_at,
        )
        .order_by(Booking.starts_at, Booking.id)
    ).all()

    revenue = _ZERO
    confirmed_revenue = _ZERO
    estimated_revenue = _ZERO
    visits_count = 0
    confirmed_visits_count = 0
    assumed_visits_count = 0
    cancelled_count = 0
    no_show_count = 0
    unknown_price_count = 0
    unique_client_ids: set = set()

    day_values: dict[date, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "revenue": _ZERO,
            "visits": 0,
            "confirmed": 0,
            "assumed": 0,
        }
    )
    catalog_counts: dict[tuple[str, str], int] = defaultdict(int)
    client_values: dict[object, dict[str, object]] = {}

    for booking, client, service in rows:
        if booking.status == BookingStatus.cancelled:
            cancelled_count += 1
            continue
        if booking.status == BookingStatus.no_show:
            no_show_count += 1
            continue

        is_confirmed_visit = booking.status == BookingStatus.completed
        is_assumed_visit = (
            booking.status == BookingStatus.scheduled and booking.ends_at <= current
        )
        if not is_confirmed_visit and not is_assumed_visit:
            continue

        visits_count += 1
        unique_client_ids.add(client.id)
        local_day = booking.starts_at.astimezone(timezone).date()
        day_values[local_day]["visits"] += 1
        if is_confirmed_visit:
            confirmed_visits_count += 1
            day_values[local_day]["confirmed"] += 1
        else:
            assumed_visits_count += 1
            day_values[local_day]["assumed"] += 1

        amount = _known_amount(booking)
        if amount is None:
            unknown_price_count += 1
        else:
            revenue += amount
            day_values[local_day]["revenue"] += amount
            is_confirmed_amount = (
                is_confirmed_visit
                and booking.price_source != "final_range_lower_bound_unconfirmed"
            )
            if is_confirmed_amount:
                confirmed_revenue += amount
            else:
                estimated_revenue += amount

        for name, kind in _catalog_items(booking, service):
            catalog_counts[(kind, name)] += 1

        client_value = client_values.setdefault(
            client.id,
            {
                "name": client.public_name,
                "revenue": _ZERO,
                "visits": 0,
                "priced_visits": 0,
            },
        )
        client_value["visits"] += 1
        if amount is not None:
            client_value["revenue"] += amount
            client_value["priced_visits"] += 1

    average_check = (
        _money(revenue / (visits_count - unknown_price_count))
        if visits_count > unknown_price_count
        else None
    )

    days: list[WebStatisticsDay] = []
    day = date_from
    while day <= date_to:
        values = day_values[day]
        days.append(
            WebStatisticsDay(
                day=day,
                revenue_amount=_money(values["revenue"]),
                visits_count=int(values["visits"]),
                confirmed_visits_count=int(values["confirmed"]),
                assumed_visits_count=int(values["assumed"]),
            )
        )
        day += timedelta(days=1)

    def catalog_items(kind: str) -> list[WebStatisticsCatalogItem]:
        result = [
            WebStatisticsCatalogItem(name=name, kind=kind, visits_count=count)
            for (item_kind, name), count in catalog_counts.items()
            if item_kind == kind
        ]
        return sorted(result, key=lambda item: (-item.visits_count, item.name.casefold()))

    clients: list[WebStatisticsClient] = []
    for client_id, values in client_values.items():
        priced_visits = int(values["priced_visits"])
        client_revenue = _money(values["revenue"])
        clients.append(
            WebStatisticsClient(
                client_id=client_id,
                client_name=str(values["name"]),
                revenue_amount=client_revenue,
                visits_count=int(values["visits"]),
                average_check_amount=(
                    _money(client_revenue / priced_visits) if priced_visits else None
                ),
            )
        )
    clients.sort(
        key=lambda item: (
            -item.revenue_amount,
            -item.visits_count,
            item.client_name.casefold(),
        )
    )

    return WebStatisticsResponse(
        date_from=date_from,
        date_to=date_to,
        timezone=timezone_name,
        generated_through=current.astimezone(timezone).date(),
        summary=WebStatisticsSummary(
            revenue_amount=_money(revenue),
            confirmed_revenue_amount=_money(confirmed_revenue),
            estimated_revenue_amount=_money(estimated_revenue),
            visits_count=visits_count,
            confirmed_visits_count=confirmed_visits_count,
            assumed_visits_count=assumed_visits_count,
            unique_clients_count=len(unique_client_ids),
            average_check_amount=average_check,
            cancelled_count=cancelled_count,
            no_show_count=no_show_count,
            unknown_price_count=unknown_price_count,
        ),
        days=days,
        procedures=catalog_items("base"),
        addons=catalog_items("addon"),
        clients=clients,
    )
