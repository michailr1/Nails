from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class WebStatisticsSummary(BaseModel):
    revenue_amount: Decimal
    confirmed_revenue_amount: Decimal
    estimated_revenue_amount: Decimal
    visits_count: int
    confirmed_visits_count: int
    assumed_visits_count: int
    unique_clients_count: int
    average_check_amount: Decimal | None
    cancelled_count: int
    no_show_count: int
    unknown_price_count: int


class WebStatisticsDay(BaseModel):
    day: date
    revenue_amount: Decimal
    visits_count: int
    confirmed_visits_count: int
    assumed_visits_count: int


class WebStatisticsCatalogItem(BaseModel):
    name: str
    kind: str
    visits_count: int
    priced_visits_count: int
    revenue_amount: Decimal


class WebStatisticsClient(BaseModel):
    client_id: uuid.UUID
    client_name: str
    revenue_amount: Decimal
    visits_count: int
    average_check_amount: Decimal | None
    last_visit_date: date | None


class WebStatisticsLongAbsentClient(BaseModel):
    client_id: uuid.UUID
    client_name: str
    last_visit_date: date
    days_since_last_visit: int
    visits_count: int


class WebStatisticsResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    generated_through: date
    long_absent_after_days: int
    long_absent_decay_days: int
    summary: WebStatisticsSummary
    days: list[WebStatisticsDay]
    procedures: list[WebStatisticsCatalogItem]
    addons: list[WebStatisticsCatalogItem]
    clients: list[WebStatisticsClient]
    long_absent_clients: list[WebStatisticsLongAbsentClient]
