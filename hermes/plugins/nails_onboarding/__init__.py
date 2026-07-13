from .handler import nails_onboarding
from .schemas import NAILS_ONBOARDING


def _registered_schema() -> dict:
    schema = dict(NAILS_ONBOARDING)
    schema["description"] = (
        f"{NAILS_ONBOARDING['description']} "
        "Every successful onboarding state response includes dialogue_guidance. "
        "Treat authoritative_current_step, do_not_reconfirm_sections, "
        "confirmation_policy and next_prompt as mandatory. Never reconfirm a section "
        "listed in do_not_reconfirm_sections, never demand a specific confirmation "
        "word, and never replace a concrete-date availability question with weekdays "
        "or a repeating weekly schedule."
    )
    return schema


def register(ctx):
    ctx.register_tool(
        name="nails_onboarding",
        toolset="nails_onboarding",
        schema=_registered_schema(),
        handler=nails_onboarding,
    )
