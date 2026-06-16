from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from api import models_db  # noqa: F401 - ensures SQLAlchemy models are registered
from api.database import Base, close_db, engine, init_db
from api.routes import stats, transactions
from fraudradar.scoring import ensure_model_artifacts
from fraudradar.settings import settings

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown.
    """
    # Startup
    logger.info("Starting %s API", settings.app_name)
    
    try:
        # Initialize database tables
        await init_db()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    try:
        # Load ML models
        ensure_model_artifacts(settings.model_dir)
        logger.info("ML models loaded")
    except Exception as e:
        logger.error(f"Failed to load ML models: {e}")
    
    logger.info("%s API started successfully", settings.app_name)
    
    yield
    
    # Shutdown
    logger.info("Shutting down %s API", settings.app_name)
    try:
        await close_db()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


app = FastAPI(
    title="FraudRadar API",
    description="Real-time fraud detection API powered by Kafka, Isolation Forest, and an Autoencoder.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware - allow all for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_request_middleware(request: Request, call_next):
    """Log all HTTP requests with method, path, status, and duration."""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        "HTTP %s %s %s %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )
    
    return response


# Include routers
app.include_router(transactions.router)
app.include_router(stats.router)

# Setup Prometheus metrics endpoint
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


# Root endpoint
@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint with links to documentation and health check."""
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=exc)
    return {
        "detail": "Internal server error",
        "path": str(request.url.path),
    }
