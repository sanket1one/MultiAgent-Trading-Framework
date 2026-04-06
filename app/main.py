from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.state import redis_manager
from api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_manager.connect()
    yield
    await redis_manager.close()

app = FastAPI(title="Multi Agent Trading Framework", lifespan=lifespan)
app.include_router(api_v1_router,  prefix="/api/v1")