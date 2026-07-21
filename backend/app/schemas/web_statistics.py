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


class WebStatisticsClient(BaseModel):
    client_id: uuid.UUID
    client_name: str
    revenue_amount: Decimal
    visits_count: int
    average_check_amount: Decimal | None


class WebStatisticsResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    generated_through: date
    summary: WebStatisticsSummary
    days: list[WebStatisticsDay]
    procedures: list[WebStatisticsCatalogItem]
    addons: list[WebStatisticsCatalogItem]
    clients: list[WebStatisticsClient]
