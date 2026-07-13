from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.onboarding import router as onboarding_router
from app.api.scheduling import router as scheduling_router
from app.config import get_settings
from app.db import get_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail fast on missing/invalid APP_TIMEZONE, DATABASE_URL, or INTERNAL_API_KEY.
    get_settings()
    get_engine()
    yield


app = FastAPI(
    title="Nails Booking API",
    version="0.3.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.include_router(onboarding_router)
app.include_router(scheduling_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def ready() -> JSONResponse:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready"},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})
