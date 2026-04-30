import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1.router import api_v1_router
from app.middleware import LatencyMiddleware
from core.database import connect_to_mongo, close_mongo_connection
from core.state import redis_manager
from core.worker import analysis_worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Number of background queue workers
NUM_WORKERS = 16


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    await redis_manager.connect()
    await connect_to_mongo()

    # Start background queue workers
    shutdown_event = asyncio.Event()
    workers = [
        asyncio.create_task(
            analysis_worker(i, redis_manager.client, shutdown_event)
        )
        for i in range(NUM_WORKERS)
    ]
    logger.info(f"Started {NUM_WORKERS} background queue workers")

    yield

    # --- Shutdown ---
    logger.info("Shutting down workers...")
    shutdown_event.set()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    await redis_manager.disconnect()
    await close_mongo_connection()


app = FastAPI(
    title="Multi-Agent Trading Framework",
    description=(
        "ReAct-style orchestration with 4 LLM analyst agents (fundamental, technical, "
        "sentiment, news) running concurrently per ticker. Redis-cached. MongoDB-persisted. "
        "Supports both sync and async (queue-based) analysis paths."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# Register latency tracking middleware
app.add_middleware(LatencyMiddleware)

app.include_router(api_v1_router, prefix="/api/v1")