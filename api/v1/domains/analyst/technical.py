from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_redis
from models.analyst import AnalysisRequest, AnalysisResult
from agents.analyst_team.technical import TechnicalAgent

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult, summary="Run technical analysis")
async def analyze_technical(
    request: AnalysisRequest,
    redis=Depends(get_redis),
) -> AnalysisResult:
    """
    Run the TechnicalAgent on a given ticker.
    Returns RSI, MACD, SMA crossover analysis with a BUY/SELL/HOLD signal.
    Results are cached in Redis for 5 minutes.
    """
    try:
        agent = TechnicalAgent(redis_client=redis)
        return await agent.analyze(request.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))