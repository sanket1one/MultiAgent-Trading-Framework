
from fastapi import APIRouter, Depends
from app.dependencies import get_redis

router = APIRouter()

@router.get("/order/{ticker}")
async def get_order(ticker: str, redis=Depends(get_redis)):
    return {"ticker": ticker, "order": "buy", "status": "pending"}