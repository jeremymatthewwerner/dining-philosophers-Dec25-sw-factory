"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import VERSION
from app.api import api_router, ws_router
from app.core.auth import get_password_hash
from app.core.config import get_settings
from app.core.database import async_session, close_db, get_db, init_db
from app.exceptions import BillingError
from app.models import User

settings = get_settings()
logger = logging.getLogger(__name__)


async def create_admin_user() -> None:
    """Create the default admin user if it doesn't exist."""
    async with async_session() as db:
        # Check if admin user exists
        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()

        if not admin:
            # Create admin user with default password
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin"),
                is_admin=True,
            )
            db.add(admin)
            await db.commit()
            logger.info("Created default admin user (username: admin, password: admin)")
        else:
            logger.info("Admin user already exists")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown."""
    try:
        logger.info("Starting application...")
        logger.info(f"Database URL configured: {bool(settings.database_url)}")
        logger.info(f"Anthropic API key configured: {bool(settings.anthropic_api_key)}")

        # Startup: Initialize database
        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialized successfully")

        # Create admin user
        logger.info("Creating admin user...")
        await create_admin_user()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    yield
    # Shutdown: Close database connections
    await close_db()


app = FastAPI(
    title="Dining Philosophers API",
    description="Real-time multi-party chat with AI-simulated historical/contemporary thinkers",
    version="0.2.0",
    lifespan=lifespan,
)


# Exception handler for BillingError
@app.exception_handler(BillingError)
async def billing_error_handler(
    request: Request,  # noqa: ARG001 - FastAPI requires this parameter
    exc: BillingError,
) -> JSONResponse:
    """Handle BillingError exceptions by returning 503 Service Unavailable.

    When a BillingError occurs (e.g., quota exceeded, billing issues):
    1. Log the error for debugging
    2. Return HTTP 503 with user-friendly message
    3. TODO: File GitHub issue in background (issue #124)

    Args:
        request: The incoming request
        exc: The BillingError exception

    Returns:
        JSONResponse with 503 status code
    """
    logger.error(f"BillingError occurred: {exc.message}")
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Service temporarily unavailable due to billing or quota issues. "
            "The issue has been reported and will be addressed shortly."
        },
    )


# CORS configuration - origins from environment variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Include WebSocket routes
app.include_router(ws_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint (liveness probe).

    Returns 200 if the service process is running and can handle requests.
    Used by container orchestrators to determine if the process is alive.
    """
    return {"status": "healthy"}


@app.get("/health/ready")
async def health_ready(
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Deep health check endpoint (readiness probe).

    Verifies all dependencies are accessible and the service is ready
    to handle traffic. Returns 503 if any dependency is degraded.

    Checks:
    - Database connectivity (executes SELECT 1)

    Used by load balancers to determine if the service should receive traffic.
    """
    checks: dict[str, str] = {}

    # Database connectivity check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = f"error: {type(e).__name__}"

    # Determine overall status
    all_ok = all(v == "ok" for v in checks.values())
    status = "ready" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": status, "checks": checks},
        status_code=status_code,
    )


@app.get("/api/version")
async def version() -> dict[str, str]:
    """Version endpoint - returns application version and name."""
    return {"version": VERSION, "name": "Dining Philosophers API"}
