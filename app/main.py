import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.database.connection import SessionLocal, init_db
from app.database.seed import seed_database
from app.routes import chat
from app.services.conversation_service import ConversationNotFoundError
from app.services.openai_service import AIServiceError

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed_database(db)
    if not settings.has_openai_key:
        logger.warning("OPENAI_API_KEY is not set; /chat will return 503 until it is configured.")
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Business assistant that answers in natural language and uses backend-validated tools.",
    lifespan=lifespan,
)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

app.include_router(chat.router, prefix=settings.api_prefix)


@app.exception_handler(AIServiceError)
async def _ai_service_error(_request: Request, exc: AIServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(ConversationNotFoundError)
async def _conversation_not_found(_request: Request, exc: ConversationNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
def health() -> dict:
    database = "ok"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        database = "unavailable"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "openai_configured": settings.has_openai_key,
        "model": settings.openai_model,
    }


# Serve the built React app (frontend/dist) at "/" when it exists. This is mounted last so the
# API routes, /health and /docs above take precedence.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
