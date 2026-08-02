from __future__ import annotations

from pydantic import BaseModel, Field


class ClientRepeatLastPreview(BaseModel):
    available: bool
    service_name: str | None = None
    addon_names: list[str] = Field(default_factory=list)
    addon_quantities: dict[str, int] = Field(default_factory=dict)
