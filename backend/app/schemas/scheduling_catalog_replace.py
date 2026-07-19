from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.scheduling import ServiceCreateRequest, ServiceSummary
from app.services.normalization import normalize_public_name


class CatalogReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: list[ServiceCreateRequest] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def reject_duplicate_names(self) -> CatalogReplaceRequest:
        normalized_names = [
            normalize_public_name(service.public_name) for service in self.services
        ]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("catalog service names must be unique")
        return self


class CatalogReplaceResponse(BaseModel):
    changed: bool
    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    archived_count: int = Field(ge=0)
    services: list[ServiceSummary]
