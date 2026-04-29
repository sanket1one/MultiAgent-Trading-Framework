from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_redis
from models.analyst import AnalysisRequest, AnalysisResult
from agents.analyst_team.sentiment import SentimentAgent

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult, summary="Run sentiment analysis")
async def analyze_sentiment(
    request: AnalysisRequest,
    redis=Depends(get_redis),
) -> AnalysisResult:
    """
    Run the SentimentAgent on a given ticker.
    Fetches Finnhub social sentiment (Reddit + Twitter) and returns a BUY/SELL/HOLD signal.
    Results are cached in Redis for 5 minutes.
    """
    try:
        agent = SentimentAgent(redis_client=redis)
        return await agent.analyze(request.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
