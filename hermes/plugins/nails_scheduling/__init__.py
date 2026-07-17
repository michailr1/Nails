from .feedback_schema import SAVE_FEEDBACK
from .feedback_tool import save_feedback
from .schemas import NAILS_SCHEDULING
from .web_auth_action import nails_scheduling_with_web_auth


def register(ctx):
    ctx.register_tool(
        name="nails_scheduling",
        toolset="nails_scheduling",
        schema=NAILS_SCHEDULING,
        handler=nails_scheduling_with_web_auth,
    )
    ctx.register_tool(
        name="save_feedback",
        toolset="nails_scheduling",
        schema=SAVE_FEEDBACK,
        handler=save_feedback,
    )
