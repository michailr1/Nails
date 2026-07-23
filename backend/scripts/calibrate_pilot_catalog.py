from __future__ import annotations

import argparse
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.db import get_session_factory
from app.models import Service
from app.services.catalog_inclusions import (
    replace_included_addons,
    replace_per_unit_time_addons,
)
from app.services.normalization import normalize_public_name


@dataclass(frozen=True, slots=True)
class BaseCalibration:
    name: str
    duration_minutes: int
    buffer_after_minutes: int
    included_addons: tuple[str, ...] = ()


BASE_CALIBRATIONS = (
    BaseCalibration("Маникюр", 60, 5),
    BaseCalibration(
        "Маникюр с покрытием",
        130,
        5,
        ("Снятие", "Укрепление"),
    ),
    BaseCalibration("Педикюр", 90, 10),
    BaseCalibration(
        "Педикюр с покрытием",
        120,
        10,
        ("Снятие",),
    ),
)

ADDON_MINUTES = {
    "Снятие": 10,
    "Укрепление": 50,
    "Френч": 20,
    "Дизайн (простой)": 10,
    "Ремонт ногтя": 10,
    "Наращивание ногтя": 20,
}
PER_UNIT_TIME_ADDONS = ("Ремонт ногтя", "Наращивание ногтя")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate one pilot owner's catalog without changing prices.",
    )
    parser.add_argument("--owner-user-id", required=True, type=uuid.UUID)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes. Without this flag the command performs a dry run.",
    )
    return parser.parse_args()


def _service_map(services: list[Service]) -> dict[str, Service]:
    return {service.normalized_public_name: service for service in services}


def _require_service(by_name: dict[str, Service], name: str, kind: str) -> Service:
    service = by_name.get(normalize_public_name(name))
    if service is None:
        raise RuntimeError(f"required catalog position not found: {name}")
    if service.kind != kind:
        raise RuntimeError(f"catalog position has unexpected kind: {name} ({service.kind})")
    return service


def main() -> None:
    args = _parse_args()
    with get_session_factory()() as session:
        services = session.scalars(
            select(Service)
            .where(Service.owner_user_id == args.owner_user_id)
            .order_by(Service.public_name)
            .with_for_update()
        ).all()
        if not services:
            raise RuntimeError("pilot owner has no catalog")

        by_name = _service_map(services)
        price_snapshot = {
            service.id: (
                service.price_type,
                service.price_amount,
                service.price_min_amount,
                service.price_max_amount,
                service.price_unit,
            )
            for service in services
        }

        changed: list[str] = []
        for calibration in BASE_CALIBRATIONS:
            base = _require_service(by_name, calibration.name, "base")
            if base.duration_minutes != calibration.duration_minutes:
                base.duration_minutes = calibration.duration_minutes
                changed.append(f"{base.public_name}: duration={calibration.duration_minutes}")
            if base.buffer_after_minutes != calibration.buffer_after_minutes:
                base.buffer_after_minutes = calibration.buffer_after_minutes
                changed.append(f"{base.public_name}: after={calibration.buffer_after_minutes}")
            addons = [
                _require_service(by_name, addon_name, "addon")
                for addon_name in calibration.included_addons
            ]
            replace_included_addons(
                session,
                args.owner_user_id,
                base,
                addons,
            )
            changed.append(
                f"{base.public_name}: included={','.join(calibration.included_addons) or '-'}"
            )

        for addon_name, extra_minutes in ADDON_MINUTES.items():
            addon = _require_service(by_name, addon_name, "addon")
            if addon.extra_minutes != extra_minutes:
                addon.extra_minutes = extra_minutes
                changed.append(f"{addon.public_name}: extra={extra_minutes}")

        per_unit_addons = [
            _require_service(by_name, addon_name, "addon")
            for addon_name in PER_UNIT_TIME_ADDONS
        ]
        replace_per_unit_time_addons(session, args.owner_user_id, per_unit_addons)
        changed.append(f"per_unit_time={','.join(PER_UNIT_TIME_ADDONS)}")

        for service in services:
            current_price = (
                service.price_type,
                service.price_amount,
                service.price_min_amount,
                service.price_max_amount,
                service.price_unit,
            )
            if current_price != price_snapshot[service.id]:
                raise RuntimeError(f"price mutation detected: {service.public_name}")

        if args.apply:
            session.commit()
            status = "applied"
        else:
            session.rollback()
            status = "dry-run"

        print(f"status={status}")
        print(f"owner_user_id={args.owner_user_id}")
        print(f"changed_count={len(changed)}")
        print("prices_unchanged=true")
        for item in changed:
            print(f"change={item}")


if __name__ == "__main__":
    main()
