from __future__ import annotations

import uuid

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models import Service
from app.services.scheduling_common import SchedulingDomainError


def included_addon_ids(
    session: Session,
    owner_user_id: uuid.UUID,
    base_service_id: uuid.UUID,
    addon_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not addon_ids:
        return set()
    rows = session.execute(
        select(Service.id)
        .select_from(Service)
        .join(
            Service.__table__.metadata.tables["service_included_addons"],
            Service.id
            == Service.__table__.metadata.tables["service_included_addons"].c.addon_service_id,
        )
        .where(
            Service.__table__.metadata.tables["service_included_addons"].c.owner_user_id
            == owner_user_id,
            Service.__table__.metadata.tables["service_included_addons"].c.base_service_id
            == base_service_id,
            Service.id.in_(addon_ids),
        )
    ).scalars()
    return set(rows)


def replace_included_addons(
    session: Session,
    owner_user_id: uuid.UUID,
    base_service: Service,
    addons: list[Service],
) -> None:
    if base_service.owner_user_id != owner_user_id or base_service.kind != "base":
        raise SchedulingDomainError("base_service_not_found", status_code=404)
    if any(addon.owner_user_id != owner_user_id or addon.kind != "addon" for addon in addons):
        raise SchedulingDomainError("addon_not_found", status_code=404)

    table = Service.__table__.metadata.tables["service_included_addons"]
    session.execute(
        delete(table).where(
            table.c.owner_user_id == owner_user_id,
            table.c.base_service_id == base_service.id,
        )
    )
    if addons:
        session.execute(
            insert(table),
            [
                {
                    "owner_user_id": owner_user_id,
                    "base_service_id": base_service.id,
                    "addon_service_id": addon.id,
                }
                for addon in addons
            ],
        )
