from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.config import get_settings
from app.models import AuditEvent, Booking, Client, Service
from app.services.web_read import list_calendar, list_clients

_FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass(frozen=True, slots=True)
class ExportedFile:
    content: bytes
    media_type: str
    filename: str


def _safe_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, int | float | Decimal | date):
        return value
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def _csv_bytes(headers: list[str], rows: Iterable[list[object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe_cell(value) for value in row])
    return stream.getvalue().encode("utf-8-sig")


def _xlsx_bytes(sheet_name: str, headers: list[str], rows: Iterable[list[object]]) -> bytes:
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet(title=sheet_name)
    worksheet.append(headers)
    for row in rows:
        worksheet.append([_safe_cell(value) for value in row])
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _export_bytes(
    *,
    sheet_name: str,
    headers: list[str],
    rows: list[list[object]],
    format_name: str,
) -> tuple[bytes, str]:
    if format_name == "csv":
        return _csv_bytes(headers, rows), "text/csv; charset=utf-8"
    if format_name == "xlsx":
        return (
            _xlsx_bytes(sheet_name, headers, rows),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    raise ValueError("unsupported_export_format")


def _audit_export(
    session: Session,
    identity: RequestIdentity,
    *,
    resource: str,
    format_name: str,
    row_count: int,
) -> None:
    session.add(
        AuditEvent(
            owner_user_id=identity.user_id,
            actor_user_id=identity.user_id,
            action="web_export_created",
            object_type=resource,
            request_id=identity.request_id,
            safe_changes={"format": format_name, "row_count": row_count},
        )
    )
    session.commit()


def _calendar_headers() -> list[str]:
    return [
        "Дата и время начала",
        "Дата и время окончания",
        "Клиентка",
        "Услуга",
        "Статус",
        "Цена",
        "Валюта",
    ]


def export_calendar(
    session: Session,
    identity: RequestIdentity,
    *,
    date_from: date,
    date_to: date,
    format_name: str,
) -> ExportedFile:
    data = list_calendar(
        session,
        identity,
        date_from=date_from,
        date_to=date_to,
    )
    rows = [
        [
            item.starts_at,
            item.ends_at,
            item.client_name,
            item.service_name,
            item.status,
            item.price_amount,
            item.currency,
        ]
        for item in data.bookings
    ]
    content, media_type = _export_bytes(
        sheet_name="Календарь",
        headers=_calendar_headers(),
        rows=rows,
        format_name=format_name,
    )
    _audit_export(
        session,
        identity,
        resource="calendar",
        format_name=format_name,
        row_count=len(rows),
    )
    return ExportedFile(
        content=content,
        media_type=media_type,
        filename=f"calendar-{date_from}-{date_to}.{format_name}",
    )


def export_all_calendar(
    session: Session,
    identity: RequestIdentity,
    *,
    format_name: str,
) -> ExportedFile:
    timezone = ZoneInfo(get_settings().app_timezone)
    records = session.execute(
        select(Booking, Client.public_name, Service.public_name)
        .join(Client, Client.id == Booking.client_id)
        .join(Service, Service.id == Booking.service_id)
        .where(
            Booking.owner_user_id == identity.user_id,
            Client.owner_user_id == identity.user_id,
            Service.owner_user_id == identity.user_id,
        )
        .order_by(Booking.starts_at, Booking.id)
    ).all()
    rows = [
        [
            booking.starts_at.astimezone(timezone),
            booking.ends_at.astimezone(timezone),
            client_name,
            service_name,
            booking.status.value,
            booking.price_amount,
            booking.currency,
        ]
        for booking, client_name, service_name in records
    ]
    content, media_type = _export_bytes(
        sheet_name="Весь календарь",
        headers=_calendar_headers(),
        rows=rows,
        format_name=format_name,
    )
    _audit_export(
        session,
        identity,
        resource="calendar_all",
        format_name=format_name,
        row_count=len(rows),
    )
    generated_on = datetime.now(UTC).astimezone(timezone).date()
    return ExportedFile(
        content=content,
        media_type=media_type,
        filename=f"calendar-all-{generated_on}.{format_name}",
    )


def export_clients(
    session: Session,
    identity: RequestIdentity,
    *,
    format_name: str,
) -> ExportedFile:
    data = list_clients(session, identity)
    headers = [
        "Имя",
        "Телефон",
        "Канал связи",
        "День рождения",
        "Заметки",
        "Ногти и кожа",
        "Чувствительность",
        "Предпочтения по стилю",
        "Предпочтения по общению",
        "Статус",
    ]
    rows = [
        [
            item.public_name,
            item.phone,
            item.contact_channel,
            item.birthday,
            item.notes,
            item.nail_skin_notes,
            item.sensitivity_notes,
            item.style_preferences,
            item.communication_preferences,
            item.profile_status,
        ]
        for item in data.clients
    ]
    content, media_type = _export_bytes(
        sheet_name="Клиентки",
        headers=headers,
        rows=rows,
        format_name=format_name,
    )
    _audit_export(
        session,
        identity,
        resource="clients",
        format_name=format_name,
        row_count=len(rows),
    )
    generated_on = datetime.now(UTC).date()
    return ExportedFile(
        content=content,
        media_type=media_type,
        filename=f"clients-all-{generated_on}.{format_name}",
    )
