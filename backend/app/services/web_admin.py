from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RequestIdentity
from app.models import AuditEvent, OnboardingState, OnboardingStatus, User, UserRole
from app.schemas.web_admin import AdminMasterCard


class AdminDomainError(Exception):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class AdminMasterCreateResult:
    master: User
    created: bool


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
    if existing is not None:
        if existing.role == UserRole.master:
            return AdminMasterCreateResult(master=existing, created=False)
        raise AdminDomainError("telegram_identity_conflict", 409)

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
    session.add(
        AuditEvent(
            owner_user_id=master.id,
            actor_user_id=identity.user_id,
            action="admin.master.create",
            object_type="user",
            object_id=master.id,
            request_id=identity.request_id,
            safe_changes={
                "telegram_user_id_suffix": str(telegram_user_id)[-4:],
                "role": "master",
            },
        )
    )
    session.commit()
    session.refresh(master)
    return AdminMasterCreateResult(master=master, created=True)
