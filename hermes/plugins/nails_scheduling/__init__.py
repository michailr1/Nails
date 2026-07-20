import os

from .feedback_schema import SAVE_FEEDBACK
from .feedback_tool import save_feedback
from .schemas import NAILS_SCHEDULING
from .tools import nails_scheduling
from .web_login_schema import WEB_LOGIN
from .web_login_tool import web_login

PORTAL_URL = "https://de.funti.cc"


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
