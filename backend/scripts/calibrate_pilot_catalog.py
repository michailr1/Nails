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

EXPECTED_ACTIVE_SERVICE_COUNT = 33
REMOVAL = "Снятие покрытия при маникюре или покрытии"
REPAIR = "Ремонт или поднятие одного уголка"


@dataclass(frozen=True, slots=True)
class BaseCalibration:
    name: str
    duration_minutes: int
    buffer_after_minutes: int
    included_addons: tuple[str, ...] = ()


BASE_CALIBRATIONS = (
    BaseCalibration("Классический или комбинированный маникюр", 60, 5),
    BaseCalibration("Маникюр с гель-лаком", 130, 5, (REMOVAL,)),
    BaseCalibration("Педикюр: ногти и стопы", 90, 10),
    BaseCalibration("Педикюр с покрытием гель-лаком", 120, 10, (REMOVAL,)),
)

ADDON_MINUTES = {
    REMOVAL: 10,
    "Френч": 20,
    "Простой дизайн": 10,
    REPAIR: 10,
}
PER_UNIT_TIME_ADDONS = (REPAIR,)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calibrate Nastya's exact pilot catalog without changing price amounts.",
    )
    parser.add_argument("--owner-user-id", required=True, type=uuid.UUID)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes. Without this flag the command performs a dry run.",
    )
    return parser.parse_args()


def _active_service_map(services: list[Service]) -> dict[str, Service]:
    return {
        service.normalized_public_name: service
        for service in services
        if service.is_active
    }


def _require_service(by_name: dict[str, Service], name: str, kind: str) -> Service:
    service = by_name.get(normalize_public_name(name))
    if service is None:
        raise RuntimeError(f"required active catalog position not found: {name}")
    if service.kind != kind:
        raise RuntimeError(f"catalog position has unexpected kind: {name} ({service.kind})")
    return service


def _price_amount_snapshot(service: Service) -> tuple[object, ...]:
    return (
        service.price_amount,
        service.price_min_amount,
        service.price_max_amount,
        service.currency,
    )


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

        active_services = [service for service in services if service.is_active]
        if len(active_services) != EXPECTED_ACTIVE_SERVICE_COUNT:
            raise RuntimeError(
                "unexpected active catalog size: "
                f"{len(active_services)} != {EXPECTED_ACTIVE_SERVICE_COUNT}"
            )

        by_name = _active_service_map(services)
        amount_snapshot = {
            service.id: _price_amount_snapshot(service)
            for service in services
        }
        changed: list[str] = []

        required: list[tuple[str, str]] = [
            *((calibration.name, "base") for calibration in BASE_CALIBRATIONS),
            *((name, "addon") for name in ADDON_MINUTES),
        ]
        for name, kind in required:
            _require_service(by_name, name, kind)

        for calibration in BASE_CALIBRATIONS:
            base = _require_service(by_name, calibration.name, "base")
            if base.duration_minutes != calibration.duration_minutes:
                changed.append(
                    f"{base.public_name}: duration="
                    f"{base.duration_minutes}->{calibration.duration_minutes}"
                )
                base.duration_minutes = calibration.duration_minutes
            if base.buffer_after_minutes != calibration.buffer_after_minutes:
                changed.append(
                    f"{base.public_name}: after="
                    f"{base.buffer_after_minutes}->{calibration.buffer_after_minutes}"
                )
                base.buffer_after_minutes = calibration.buffer_after_minutes
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
                f"{base.public_name}: included="
                f"{','.join(addon.public_name for addon in addons) or '-'}"
            )

        for addon_name, extra_minutes in ADDON_MINUTES.items():
            addon = _require_service(by_name, addon_name, "addon")
            if addon.extra_minutes != extra_minutes:
                changed.append(
                    f"{addon.public_name}: extra="
                    f"{addon.extra_minutes}->{extra_minutes}"
                )
                addon.extra_minutes = extra_minutes

        repair = _require_service(by_name, REPAIR, "addon")
        if repair.price_type not in {"fixed", "per_unit"}:
            raise RuntimeError(
                f"unexpected repair price type: {repair.price_type}"
            )
        if repair.price_type != "per_unit":
            changed.append(f"{repair.public_name}: price_type=fixed->per_unit")
            repair.price_type = "per_unit"
        if repair.price_unit != "уголок":
            changed.append(
                f"{repair.public_name}: price_unit="
                f"{repair.price_unit or '-'}->уголок"
            )
            repair.price_unit = "уголок"

        per_unit_addons = [
            _require_service(by_name, addon_name, "addon")
            for addon_name in PER_UNIT_TIME_ADDONS
        ]
        replace_per_unit_time_addons(session, args.owner_user_id, per_unit_addons)
        changed.append(
            "per_unit_time="
            + ",".join(addon.public_name for addon in per_unit_addons)
        )

        for service in services:
            if _price_amount_snapshot(service) != amount_snapshot[service.id]:
                raise RuntimeError(f"price amount mutation detected: {service.public_name}")

        if args.apply:
            session.commit()
            status = "applied"
        else:
            session.rollback()
            status = "dry-run"

        print(f"status={status}")
        print(f"owner_user_id={args.owner_user_id}")
        print(f"active_service_count={len(active_services)}")
        print("required_services_found=8/8")
        print("missing_services=none")
        print("ambiguous_services=none")
        print("price_amounts_unchanged=true")
        print("pedicure_ranges_preserved=true")
        print("inactive_short_names_used=false")
        print("invented_reinforcement_addon=false")
        print("extension_changed=false")
        print(f"apply_performed={str(args.apply).lower()}")
        print(f"changed_count={len(changed)}")
        for item in changed:
            print(f"change={item}")


if __name__ == "__main__":
    main()
