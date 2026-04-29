from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_redis
from models.analyst import AnalysisRequest, AnalysisReport
from agents.orchestrator import ReActOrchestrator

router = APIRouter()


@router.post("/analyze", response_model=AnalysisReport, summary="Run full multi-agent analysis")
async def execute_full_analysis(
    request: AnalysisRequest,
    redis=Depends(get_redis),
) -> AnalysisReport:
    """
    Run the full ReActOrchestrator pipeline for a given ticker.

    Concurrently executes all 4 analyst agents (fundamental, technical,
    sentiment, news), aggregates their signals via weighted majority vote,
    and returns a unified AnalysisReport.

    The report is persisted to MongoDB for chat history.
    Individual agent results are Redis-cached for 5 minutes.
    """
    try:
        orchestrator = ReActOrchestrator(redis_client=redis)
        return await orchestrator.run(
            ticker=request.ticker,
            session_id=request.session_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", summary="Retrieve analysis history for a session")
async def get_analysis_history(session_id: str):
    """
    Retrieve all analysis reports stored in MongoDB for a given session ID.
    """
    from core.chat_repository import ChatRepository
    try:
        repo = ChatRepository()
        return await repo.get_history(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))