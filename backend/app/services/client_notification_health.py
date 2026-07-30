from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.client_notification_models import ClientNotificationOutbox
from app.schemas.client_notifications import ClientNotificationQueueHealth


def notification_queue_health(session: Session) -> ClientNotificationQueueHealth:
    pending_count = session.scalar(
        select(func.count(ClientNotificationOutbox.id)).where(
            ClientNotificationOutbox.status == "pending"
        )
    )
    claimed_count = session.scalar(
        select(func.count(ClientNotificationOutbox.id)).where(
            ClientNotificationOutbox.status == "claimed"
        )
    )
    failed_count = session.scalar(
        select(func.count(ClientNotificationOutbox.id)).where(
            ClientNotificationOutbox.status == "failed"
        )
    )
    oldest_pending = session.scalar(
        select(func.min(ClientNotificationOutbox.created_at)).where(
            ClientNotificationOutbox.status == "pending"
        )
    )
    age = None
    if oldest_pending is not None:
        age = max(0, int((datetime.now(UTC) - oldest_pending).total_seconds()))
    return ClientNotificationQueueHealth(
        pending_count=int(pending_count or 0),
        claimed_count=int(claimed_count or 0),
        failed_count=int(failed_count or 0),
        oldest_pending_age_seconds=age,
    )
