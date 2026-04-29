from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.state import redis_manager
from core.database import connect_to_mongo, close_mongo_connection
from api.v1.router import api_v1_router
import logging

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_manager.connect()
    await connect_to_mongo()
    yield
    # Shutdown
    await redis_manager.disconnect()
    await close_mongo_connection()


app = FastAPI(
    title="Multi-Agent Trading Framework",
    description=(
        "ReAct-style orchestration with 4 LLM analyst agents (fundamental, technical, "
        "sentiment, news) running concurrently per ticker. Redis-cached. MongoDB-persisted."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(api_v1_router, prefix="/api/v1")