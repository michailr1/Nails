from .schemas import NAILS_SCHEDULING
from .tools import nails_scheduling


def register(ctx):
    ctx.register_tool(
        name="nails_scheduling",
        toolset="nails_scheduling",
        schema=NAILS_SCHEDULING,
        handler=nails_scheduling,
    )
