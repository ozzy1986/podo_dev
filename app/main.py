"""
FastAPI application factory with lifespan management.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.middleware import (
    LoggingMiddleware,
    ErrorHandlerMiddleware,
    RateLimitMiddleware,
    setup_cors,
    setup_exception_handlers,
)
from app.db.postgresql import PostgreSQLDatabase, set_pg_pool
from app.db.clickhouse import ClickHouseDatabase, set_ch_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    
    Args:
        app: FastAPI application instance
    
    Yields:
        None (control to application)
    """
    # Startup (each step logged so 502 can be diagnosed from logs)
    logger.info("Starting application...")
    settings = get_settings()
    
    try:
        settings.validate_production_config()
    except ValueError as e:
        logger.critical(f"Configuration error: {e}")
        raise
    
    logger.info("Connecting to PostgreSQL at %s:%s...", settings.database.host, settings.database.port)
    try:
        pg_db = PostgreSQLDatabase(settings.database)
        await pg_db.connect()
        set_pg_pool(pg_db)
        logger.info("PostgreSQL pool initialized")
    except Exception as e:
        logger.exception("PostgreSQL connection failed: %s", e)
        raise
    
    logger.info("Connecting to ClickHouse at %s:%s...", settings.clickhouse.host, settings.clickhouse.port)
    try:
        ch_db = ClickHouseDatabase(settings.clickhouse)
        ch_db.connect()
        set_ch_client(ch_db)
        logger.info("ClickHouse client initialized")
    except Exception as e:
        logger.exception("ClickHouse connection failed: %s", e)
        raise
    
    logger.info("Starting background scheduler...")
    try:
        from app.workers.scheduler import start_scheduler, stop_scheduler
        await start_scheduler()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.exception("Scheduler startup failed: %s", e)
        raise
    
    logger.info("Application startup complete; API is ready to accept requests")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop background scheduler
    try:
        from app.workers.scheduler import stop_scheduler
        await stop_scheduler()
        logger.info("Background scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
    
    # Close ClickHouse client
    try:
        ch_db.disconnect()
        logger.info("ClickHouse client closed")
    except Exception as e:
        logger.error(f"Error closing ClickHouse client: {e}")
    
    # Close PostgreSQL pool
    try:
        await pg_db.disconnect()
        logger.info("PostgreSQL pool closed")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL pool: {e}")
    
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    settings = get_settings()
    
    # Configure logging (console + file)
    import os
    from logging.handlers import RotatingFileHandler

    log_level = getattr(logging, settings.log_level.upper())
    log_format = logging.Formatter(settings.log_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # File handler (logs/ directory)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), settings.log_dir)
    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)

    # JSON-structured error log for production monitoring
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    root_logger.addHandler(error_handler)
    
    # Create FastAPI app
    app = FastAPI(
        title="d.onl API",
        description="Domain ownership mining and token distribution platform",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan
    )
    
    # Add middleware (order matters: last added = first executed)
    setup_cors(app, settings.security.get_cors_origins_list())
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RateLimitMiddleware,
                       rate_per_minute=settings.security.rate_limit_per_minute,
                       burst=settings.security.rate_limit_burst)
    app.add_middleware(LoggingMiddleware)

    # Register exception handlers for consistent error envelope
    setup_exception_handlers(app)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return JSONResponse(
            content={
                "status": "healthy",
                "environment": settings.app_env,
                "version": "2.0.0"
            }
        )
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return JSONResponse(
            content={
                "service": "d.onl API",
                "version": "2.0.0",
                "docs": "/api/docs" if settings.debug else None
            }
        )
    
    # Include API routers
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix="/api")
    
    logger.info(f"FastAPI application created (env={settings.app_env})")
    
    return app


# Create application instance
app = create_app()
