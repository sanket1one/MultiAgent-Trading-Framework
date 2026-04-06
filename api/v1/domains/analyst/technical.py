from fastapi import APIRouter, Depends
from app.dependencies import get_redis

router = APIRouter()

@router.get("/indicator/{ticker}")
async def get_indicator(ticker: str, redis=Depends(get_redis)):
    return {"ticker": ticker, "indicator": "RSI", "value": 50}