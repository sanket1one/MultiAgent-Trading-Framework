from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_redis
from models.analyst import AnalysisRequest, AnalysisResult
from agents.analyst_team.news import NewsAgent

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult, summary="Run news analysis")
async def analyze_news(
    request: AnalysisRequest,
    redis=Depends(get_redis),
) -> AnalysisResult:
    """
    Run the NewsAgent on a given ticker.
    Fetches recent Finnhub headlines and returns a BUY/SELL/HOLD signal.
    Results are cached in Redis for 5 minutes.
    """
    try:
        agent = NewsAgent(redis_client=redis)
        return await agent.analyze(request.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))