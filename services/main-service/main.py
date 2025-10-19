"""Main application entry point."""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import redis
import redis.asyncio as aioredis
import httpx
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from config import REDIS_URL, API_VERSION
import database
import schemas
import auth
import dependencies
from database import init_db, engine
from monitoring import init_profiling
from logging_config import setup_logging
from routers import products, cart, orders, auth as auth_router
from redis_rate_limiter import RedisRateLimiter

# Setup structured logging
setup_logging()
logger = logging.getLogger(__name__)


# Initialize Redis clients globally
# Sync client for middleware (rate limiter must be sync)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
# Async client for customer segmentation
async_redis_client = None  # Will be initialized in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")

    # Initialize database
    init_db()

    # Instrument and attach Redis clients
    RedisInstrumentor().instrument(redis_client=redis_client)
    app.state.redis_client = redis_client

    # Initialize async Redis client for customer segmentation
    global async_redis_client
    async_redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    # Instrument async Redis client for tracing
    RedisInstrumentor().instrument(redis_client=async_redis_client)
    app.state.async_redis_client = async_redis_client
    logger.info("Redis clients initialized (sync + async)")

    # Initialize HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)
    HTTPXClientInstrumentor().instrument_client(http_client)
    app.state.http_client = http_client
    logger.info("HTTP client initialized")

    # Initialize profiling
    init_profiling()

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await http_client.aclose()
    await async_redis_client.aclose()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="WebStore Main Service",
    version=API_VERSION,
    lifespan=lifespan
)

# Security middleware with Redis-backed dual-tier rate limiting
app.add_middleware(
    RedisRateLimiter,
    redis_client=redis_client,
    requests_per_minute_ip=50000,    # High limit for demo with all traffic from localhost
    requests_per_minute_user=5000    # High limit for demo traffic
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument FastAPI and SQLAlchemy
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

# Include routers
app.include_router(auth_router.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)

# For backward compatibility, also add checkout endpoint at /checkout
@app.post("/checkout")
async def checkout_compat(
    request: schemas.CheckoutRequest,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.verify_token),
    order_service = Depends(dependencies.get_order_service)
):
    """Backward compatible checkout endpoint."""
    return await orders.checkout(request, db, token, order_service)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
