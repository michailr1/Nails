from .schemas import NAILS_ONBOARDING
from .tools import nails_onboarding


def register(ctx):
    ctx.register_tool(
        name="nails_onboarding",
        toolset="nails_onboarding",
        schema=NAILS_ONBOARDING,
        handler=nails_onboarding,
    )
