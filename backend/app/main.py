import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.api.routes.ingest import router as ingest_router
from backend.api.routes.analyze import router as analyze_router
from backend.api.routes.hosts import router as hosts_router
from backend.api.routes.metrics import router as metrics_router
from backend.api.routes.alerts import router as alerts_router
from backend.api.routes.processes import router as processes_router
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.disk_analyzer import router as disk_analyzer_router
from backend.api.routes.auth import router as auth_router

from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


import asyncio
from backend.worker.run_worker import worker_loop
from backend.db.auto_migrate import auto_migrate_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager replacing deprecated startup/shutdown events."""
    logger.info("AI Infra Monitor Backend starting up...")
    # 1. Run automatic schema migration to guarantee all columns exist
    auto_migrate_schema()
    # 2. Start background worker task inside the web service
    worker_task = asyncio.create_task(worker_loop())
    yield
    worker_task.cancel()
    logger.info("AI Infra Monitor Backend shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="AI Infra Monitor Backend",
    description="Backend API for AI Infrastructure Monitoring",
    version="0.1.0",
    lifespan=lifespan
)

import os

# Configure CORS - Allow all origins including Vercel preview deployments, production domains, and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.getenv("ALLOWED_ORIGINS") == "*" else [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ai-infra-monitor.vercel.app"
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:.*|http://127\.0\.0\.1:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])
app.include_router(analyze_router, prefix="/api/v1", tags=["analyze"])
app.include_router(hosts_router, prefix="/api/v1", tags=["hosts"])
app.include_router(metrics_router, prefix="/api/v1", tags=["metrics"])
app.include_router(alerts_router, prefix="/api/v1", tags=["alerts"])
app.include_router(processes_router, prefix="/api/v1", tags=["processes"])
app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
app.include_router(disk_analyzer_router, prefix="/api/v1", tags=["disk_analyzer"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])


async def check_db_connection() -> bool:
    """
    Mock database connection check.
    In a real implementation, this would verify PostgreSQL connectivity.
    
    Returns:
        bool: Always returns True for mock implementation
    """
    logger.info("Checking database connection (mock)")
    return True


async def check_redis_connection() -> bool:
    """
    Mock Redis connection check.
    In a real implementation, this would verify Redis connectivity.
    
    Returns:
        bool: Always returns True for mock implementation
    """
    logger.info("Checking Redis connection (mock)")
    return True


@app.get("/health")
async def health_check():
    """
    Health check endpoint that verifies service status.
    
    Performs mock checks for:
    - Database connectivity
    - Redis connectivity
    
    Returns:
        JSONResponse: Status object with "ok" status
    """
    logger.info("Health check requested")
    
    # Perform mock checks
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    
    # Log check results
    logger.info(f"DB check: {db_ok}, Redis check: {redis_ok}")
    
    return JSONResponse(
        status_code=200,
        content={"status": "ok"}
    )
