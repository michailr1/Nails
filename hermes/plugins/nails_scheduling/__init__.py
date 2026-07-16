from .feedback_schema import SAVE_FEEDBACK
from .feedback_tool import save_feedback
from .schemas import NAILS_SCHEDULING
from .shutdown_policy import suppress_shutdown_notifications_for_nails
from .tools import nails_scheduling


def register(ctx):
    suppress_shutdown_notifications_for_nails()
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
