from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import RequestIdentity, require_request_identity
from app.db import get_db_session
from app.schemas.scheduling_catalog_replace import CatalogReplaceRequest, CatalogReplaceResponse
from app.services.scheduling_catalog_replace import replace_catalog

router = APIRouter(prefix="/api/v1/scheduling", tags=["scheduling"])
SessionDependency = Annotated[Session, Depends(get_db_session)]
IdentityDependency = Annotated[RequestIdentity, Depends(require_request_identity)]


@router.put("/services/catalog", response_model=CatalogReplaceResponse)
def replace_service_catalog(
    body: CatalogReplaceRequest,
    session: SessionDependency,
    identity: IdentityDependency,
) -> CatalogReplaceResponse:
    return replace_catalog(session, identity, body)
