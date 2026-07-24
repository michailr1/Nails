from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, OnboardingState, OnboardingStatus, User, UserRole
from app.schemas.web_admin import AdminMasterCard
from app.services.hermes_access import HermesAccessError, get_hermes_access_client
from app.web_auth_models import WebSession


class AdminDomainError(Exception):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class AdminMasterCreateResult:
    master: User
    created: bool
    reactivated: bool = False


@dataclass(frozen=True, slots=True)
class AdminMasterDisableResult:
    master: User
    changed: bool


def require_admin(identity: RequestIdentity) -> None:
    if identity.role != UserRole.admin:
        raise AdminDomainError("admin_required", 403)


def master_card(user: User) -> AdminMasterCard:
    onboarding_status = (
        user.onboarding_state.status.value
        if user.onboarding_state is not None
        else OnboardingStatus.not_started.value
    )
    return AdminMasterCard(
        id=user.id,
        telegram_user_id=user.telegram_user_id,
        is_active=user.is_active,
        onboarding_status=onboarding_status,
        created_at=user.created_at,
    )


def list_masters(session: Session, identity: RequestIdentity) -> list[User]:
    require_admin(identity)
    return list(
        session.scalars(
            select(User)
            .where(User.role == UserRole.master)
            .order_by(User.created_at.desc(), User.id)
        ).all()
    )


def _grant(telegram_user_id: int):
    try:
        return get_hermes_access_client().grant(telegram_user_id)
    except HermesAccessError as exc:
        raise AdminDomainError(str(exc), 503) from exc


def _revoke(telegram_user_id: int):
    try:
        return get_hermes_access_client().revoke(telegram_user_id)
    except HermesAccessError as exc:
        raise AdminDomainError(str(exc), 503) from exc


def create_master(
    session: Session,
    identity: RequestIdentity,
    *,
    telegram_user_id: int,
) -> AdminMasterCreateResult:
    require_admin(identity)

    existing = session.scalar(
        select(User).where(User.telegram_user_id == telegram_user_id)
    )
    if existing is not None and existing.role != UserRole.master:
        raise AdminDomainError("telegram_identity_conflict", 409)

    access = _grant(telegram_user_id)
    if existing is not None and existing.is_active:
        return AdminMasterCreateResult(master=existing, created=False)

    try:
        if existing is not None:
            existing.is_active = True
            master = existing
            action = "admin.master.reactivate"
            created = False
            reactivated = True
        else:
            master = User(
                telegram_user_id=telegram_user_id,
                role=UserRole.master,
                is_active=True,
            )
            session.add(master)
            session.flush()
            session.add(
                OnboardingState(
                    user_id=master.id,
                    status=OnboardingStatus.not_started,
                )
            )
            action = "admin.master.create"
            created = True
            reactivated = False

        session.add(
            AuditEvent(
                owner_user_id=master.id,
                actor_user_id=identity.user_id,
                action=action,
                object_type="user",
                object_id=master.id,
                request_id=identity.request_id,
                safe_changes={
                    "telegram_user_id_suffix": str(telegram_user_id)[-4:],
                    "role": "master",
                    "is_active": True,
                },
            )
        )
        session.commit()
        session.refresh(master)
        return AdminMasterCreateResult(
            master=master,
            created=created,
            reactivated=reactivated,
        )
    except SQLAlchemyError:
        session.rollback()
        if access.changed:
            try:
                get_hermes_access_client().revoke(telegram_user_id)
            except HermesAccessError:
                raise AdminDomainError("master_create_compensation_failed", 503) from None
        raise


def disable_master(
    session: Session,
    identity: RequestIdentity,
    *,
    master_user_id: uuid.UUID,
) -> AdminMasterDisableResult:
    require_admin(identity)
    master = session.scalar(
        select(User).where(
            User.id == master_user_id,
            User.role == UserRole.master,
        )
    )
    if master is None:
        raise AdminDomainError("master_not_found", 404)

    access = _revoke(master.telegram_user_id)
    if not master.is_active:
        return AdminMasterDisableResult(master=master, changed=False)

    now = datetime.now(UTC)
    try:
        master.is_active = False
        session.execute(
            update(WebSession)
            .where(WebSession.user_id == master.id, WebSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        session.execute(
            update(WebSession)
            .where(WebSession.target_owner_user_id == master.id)
            .values(target_owner_user_id=None)
        )
        session.add(
            AuditEvent(
                owner_user_id=master.id,
                actor_user_id=identity.user_id,
                action="admin.master.disable",
                object_type="user",
                object_id=master.id,
                request_id=identity.request_id,
                safe_changes={"is_active": False},
            )
        )
        session.commit()
        session.refresh(master)
        return AdminMasterDisableResult(master=master, changed=True)
    except SQLAlchemyError:
        session.rollback()
        if access.changed:
            try:
                get_hermes_access_client().grant(master.telegram_user_id)
            except HermesAccessError:
                raise AdminDomainError("master_disable_compensation_failed", 503) from None
        raise
