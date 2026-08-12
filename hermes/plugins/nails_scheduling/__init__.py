import os

from .feedback_schema import SAVE_FEEDBACK
from .feedback_tool import save_feedback
from .portal import PORTAL_URL
from .schemas import NAILS_SCHEDULING
from .tools import nails_scheduling
from .web_login_schema import WEB_LOGIN
from .web_login_tool import web_login

_EFFECTIVE_SCHEDULE_CONTRACT = (
    "When the master asks about working hours, why client slots stop early, whether a "
    "date is a day off, or what clients can currently book, never answer from reusable "
    "default_work_intervals alone. Resolve the concrete date when needed and call "
    "action=day_view. Treat dated availability from that result as the effective "
    "client-visible work window. Explain that concrete free slots are further reduced "
    "by service duration, preparation and cleanup buffers, and existing bookings. "
    "Default work intervals are only a reusable template and must never be described "
    "as the current factual schedule. If no concrete date was provided, ask for the "
    "date instead of claiming that working hours are not saved."
)

if _EFFECTIVE_SCHEDULE_CONTRACT not in NAILS_SCHEDULING["description"]:
    NAILS_SCHEDULING["description"] = (
        f"{NAILS_SCHEDULING['description']} {_EFFECTIVE_SCHEDULE_CONTRACT}"
    )


def open_master_portal(raw_args: str) -> str:
    del raw_args
    return f"Личный кабинет мастера: {PORTAL_URL}"


def register(ctx):
    ctx.register_tool(
        name="nails_scheduling",
        toolset="nails_scheduling",
        schema=NAILS_SCHEDULING,
        handler=nails_scheduling,
    )
    ctx.register_tool(
        name="save_feedback",
        toolset="nails_scheduling",
        schema=SAVE_FEEDBACK,
        handler=save_feedback,
    )
    register_command = getattr(ctx, "register_command", None)
    if register_command is not None:
        register_command(
            "portal",
            handler=open_master_portal,
            description="Личный кабинет мастера",
        )
    if os.getenv("NAILS_WEB_LOGIN_TOOL_ENABLED", "").strip().lower() == "true":
        ctx.register_tool(
            name="web_login",
            toolset="nails_scheduling",
            schema=WEB_LOGIN,
            handler=web_login,
        )
