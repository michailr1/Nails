from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKeyConstraint, Table, delete, func, insert, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Service
from app.services.scheduling_common import SchedulingDomainError

service_included_addons = Table(
    "service_included_addons",
    Base.metadata,
    Column("owner_user_id", UUID(as_uuid=True), nullable=False),
    Column("base_service_id", UUID(as_uuid=True), nullable=False),
    Column("addon_service_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(
        ["owner_user_id", "base_service_id"],
        ["services.owner_user_id", "services.id"],
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ["owner_user_id", "addon_service_id"],
        ["services.owner_user_id", "services.id"],
        ondelete="CASCADE",
    ),
    extend_existing=True,
)

service_per_unit_time_addons = Table(
    "service_per_unit_time_addons",
    Base.metadata,
    Column("owner_user_id", UUID(as_uuid=True), nullable=False),
    Column("addon_service_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(
        ["owner_user_id", "addon_service_id"],
        ["services.owner_user_id", "services.id"],
        ondelete="CASCADE",
    ),
    extend_existing=True,
)


def included_addon_ids(
    session: Session,
    owner_user_id: uuid.UUID,
    base_service_id: uuid.UUID,
    addon_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not addon_ids:
        return set()
    rows = session.scalars(
        select(service_included_addons.c.addon_service_id).where(
            service_included_addons.c.owner_user_id == owner_user_id,
            service_included_addons.c.base_service_id == base_service_id,
            service_included_addons.c.addon_service_id.in_(addon_ids),
        )
    )
    return set(rows)


def per_unit_time_addon_ids(
    session: Session,
    owner_user_id: uuid.UUID,
    addon_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not addon_ids:
        return set()
    rows = session.scalars(
        select(service_per_unit_time_addons.c.addon_service_id).where(
            service_per_unit_time_addons.c.owner_user_id == owner_user_id,
            service_per_unit_time_addons.c.addon_service_id.in_(addon_ids),
        )
    )
    return set(rows)


def _ensure_addons(owner_user_id: uuid.UUID, addons: list[Service]) -> None:
    if any(addon.owner_user_id != owner_user_id or addon.kind != "addon" for addon in addons):
        raise SchedulingDomainError("addon_not_found", status_code=404)


def replace_included_addons(
    session: Session,
    owner_user_id: uuid.UUID,
    base_service: Service,
    addons: list[Service],
) -> None:
    if base_service.owner_user_id != owner_user_id or base_service.kind != "base":
        raise SchedulingDomainError("base_service_not_found", status_code=404)
    _ensure_addons(owner_user_id, addons)

    session.execute(
        delete(service_included_addons).where(
            service_included_addons.c.owner_user_id == owner_user_id,
            service_included_addons.c.base_service_id == base_service.id,
        )
    )
    if addons:
        session.execute(
            insert(service_included_addons),
            [
                {
                    "owner_user_id": owner_user_id,
                    "base_service_id": base_service.id,
                    "addon_service_id": addon.id,
                }
                for addon in addons
            ],
        )


def replace_per_unit_time_addons(
    session: Session,
    owner_user_id: uuid.UUID,
    addons: list[Service],
) -> None:
    _ensure_addons(owner_user_id, addons)
    session.execute(
        delete(service_per_unit_time_addons).where(
            service_per_unit_time_addons.c.owner_user_id == owner_user_id
        )
    )
    if addons:
        session.execute(
            insert(service_per_unit_time_addons),
            [
                {
                    "owner_user_id": owner_user_id,
                    "addon_service_id": addon.id,
                }
                for addon in addons
            ],
        )
