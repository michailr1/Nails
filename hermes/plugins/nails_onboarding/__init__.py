from .schemas import NAILS_ONBOARDING
from .tools import nails_onboarding

_DIALOGUE_CONTRACT = (
    "For every successful onboarding state response, treat result.current_step as "
    "the authoritative next section. Inspect each result.sections item before asking "
    "for confirmation: when is_current_revision_confirmed is true, never ask to "
    "confirm that section again unless its revision changes. One clear affirmative "
    "reply such as yes, correct or confirm to the immediately preceding summary is "
    "enough; never demand a particular word. When current_step is availability, ask "
    "only for concrete nearby calendar dates or an exact date range. Never ask for "
    "weekdays alone or a repeating weekly schedule. In summaries, preserve the exact "
    "ISO calendar date returned by the tool. Do not add or infer a weekday label unless "
    "it was deterministically supplied by a trusted tool; an unverified weekday must "
    "be omitted. A successful complete operation materializes the confirmed onboarding "
    "data into working scheduling tables. State that setup is complete and data is "
    "activated, but do not promise creating or changing bookings, changing settings, "
    "or calculating free slots until a restricted calendar tool for those operations "
    "is actually available."
)

if _DIALOGUE_CONTRACT not in NAILS_ONBOARDING["description"]:
    NAILS_ONBOARDING["description"] = (
        f"{NAILS_ONBOARDING['description']} {_DIALOGUE_CONTRACT}"
    )


def register(ctx):
    ctx.register_tool(
        name="nails_onboarding",
        toolset="nails_onboarding",
        schema=NAILS_ONBOARDING,
        handler=nails_onboarding,
    )
