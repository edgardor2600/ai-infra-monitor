import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from backend.api.routes.ingest import router as ingest_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Infra Monitor Backend",
    description="Backend API for AI Infrastructure Monitoring",
    version="0.1.0"
)

# Include routers
app.include_router(ingest_router, prefix="/api/v1/ingest", tags=["ingest"])


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


@app.on_event("startup")
async def startup_event():
    """Log application startup"""
    logger.info("AI Infra Monitor Backend starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    """Log application shutdown"""
    logger.info("AI Infra Monitor Backend shutting down...")
