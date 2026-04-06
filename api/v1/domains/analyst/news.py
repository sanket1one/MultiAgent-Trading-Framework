from fastapi import APIRouter, Depends
from app.dependencies import get_redis

router = APIRouter()

@router.get("/twitter/{user_id}")
async def get_twitter_sentiment(user_id: str, redis=Depends(get_redis)):
    return {"news": "testing phase", "sentiment": "positive", "user_id": user_id}