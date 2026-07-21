from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.feedback import router as feedback_router
from app.api.onboarding import router as onboarding_router
from app.api.scheduling import router as scheduling_router
from app.api.scheduling_catalog_batch import router as scheduling_catalog_batch_router
from app.api.scheduling_digest import router as scheduling_digest_router
from app.api.web_auth import router as web_auth_router
from app.api.web_auth_conversation import router as web_auth_conversation_router
from app.api.web_booking_mutations import router as web_booking_mutations_router
from app.api.web_read import router as web_read_router
from app.config import get_settings
from app.db import get_engine
from app.web_proxy import resolve_client_ip

_WEB_STATIC_DIR = Path(__file__).resolve().parent / "web_static"
_WEB_CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "connect-src 'self'",
        "img-src 'self' data:",
        "style-src 'self'",
        "script-src 'self'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    )
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Fail fast on missing/invalid APP_TIMEZONE, DATABASE_URL, or INTERNAL_API_KEY.
    get_settings()
    get_engine()
    yield


app = FastAPI(
    title="Nails Booking API",
    version="0.4.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def normalize_web_client_ip(request: Request, call_next):
    if request.url.path.startswith("/web") and request.client is not None:
        settings = get_settings()
        client_ip = resolve_client_ip(
            peer_ip=request.client.host,
            x_real_ip=request.headers.get("x-real-ip"),
            x_forwarded_for=request.headers.get("x-forwarded-for"),
            trusted_proxy_cidrs=settings.trusted_web_proxy_cidrs,
        )
        request.scope["client"] = (client_ip, request.client.port)
    return await call_next(request)


@app.middleware("http")
async def add_web_security_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/web"):
        response.headers["Content-Security-Policy"] = _WEB_CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(onboarding_router)
app.include_router(scheduling_router)
app.include_router(scheduling_catalog_batch_router)
app.include_router(scheduling_digest_router)
app.include_router(feedback_router)
app.include_router(web_auth_router)
app.include_router(web_auth_conversation_router)
app.include_router(web_read_router)
app.include_router(web_booking_mutations_router)
app.mount(
    "/web",
    StaticFiles(directory=_WEB_STATIC_DIR, html=True),
    name="web-master-interface",
)


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
