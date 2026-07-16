from __future__ import annotations

from typing import Any

_PATCH_MARKER = "_nails_shutdown_notifications_suppressed"


def suppress_shutdown_notifications_for_nails() -> None:
    """Disable Hermes shutdown Telegram warnings for this profile only.

    This module is imported and applied only by the profile-local Nails plugin.
    Other Hermes profiles do not load this plugin and retain upstream behavior.
    """
    from gateway.run import GatewayRunner

    current = GatewayRunner._notify_active_sessions_of_shutdown
    if getattr(current, _PATCH_MARKER, False):
        return

    async def _do_not_notify_active_sessions(self: Any) -> None:
        return None

    setattr(_do_not_notify_active_sessions, _PATCH_MARKER, True)
    GatewayRunner._notify_active_sessions_of_shutdown = _do_not_notify_active_sessions
