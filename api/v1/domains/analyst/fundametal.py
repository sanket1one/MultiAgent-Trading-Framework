from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_redis
from models.analyst import AnalysisRequest, AnalysisResult
from agents.analyst_team.fundamental import FundamentalAgent

router = APIRouter()


@router.post("/analyze", response_model=AnalysisResult, summary="Run fundamental analysis")
async def analyze_fundamental(
    request: AnalysisRequest,
    redis=Depends(get_redis),
) -> AnalysisResult:
    """
    Run the FundamentalAgent on a given ticker.
    Returns P/E, EPS, margins, debt/equity analysis with a BUY/SELL/HOLD signal.
    Results are cached in Redis for 5 minutes.
    """
    try:
        agent = FundamentalAgent(redis_client=redis)
        return await agent.analyze(request.ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))