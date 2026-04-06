from fastapi import APIRouter, Depends
from app.dependencies import get_redis

router = APIRouter()

@router.get("/ratios/{ticker}")
async def get_ratios(ticker: str, redis=Depends(get_redis)):
    return {"ticker": ticker, "pe_ratio": 15.5}