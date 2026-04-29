import uuid
import time
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_redis
from models.analyst import AnalysisRequest, AnalysisReport
from agents.orchestrator import ReActOrchestrator
from core.queue import enqueue_job, get_job_status, get_job_result, get_job_error

logger = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------------------
# Sync path — existing (unchanged)
# --------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalysisReport, summary="Run full multi-agent analysis (sync)")
async def execute_full_analysis(
    request: AnalysisRequest,
    redis=Depends(get_redis),
) -> AnalysisReport:
    """
    Run the full ReActOrchestrator pipeline for a given ticker.

    Concurrently executes all 4 analyst agents (fundamental, technical,
    sentiment, news), aggregates their signals via weighted majority vote,
    and returns a unified AnalysisReport.

    This is the **synchronous** path — the response blocks until analysis completes.
    Individual agent results are Redis-cached for 5 minutes.
    """
    t0 = time.perf_counter()
    try:
        orchestrator = ReActOrchestrator(redis_client=redis)
        report = await orchestrator.run(
            ticker=request.ticker,
            session_id=request.session_id,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[Sync] {request.ticker} E2E latency: {latency_ms:.1f}ms")
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------
# Async queue path — NEW
# --------------------------------------------------------------------------

@router.post("/enqueue", status_code=202, summary="Enqueue analysis job (async)")
async def enqueue_analysis(
    request: AnalysisRequest,
    redis=Depends(get_redis),
):
    """
    Enqueue an analysis job into the Redis Stream.

    Returns immediately with a `job_id`. Use `GET /job/{job_id}` to poll for the result.
    Background workers process the job and store the result in Redis (TTL 10 min).

    This is the **asynchronous** path — ideal for burst traffic.
    """
    try:
        job_id = await enqueue_job(
            redis_client=redis,
            ticker=request.ticker,
            session_id=request.session_id,
        )
        return {
            "job_id": job_id,
            "ticker": request.ticker.upper(),
            "status": "pending",
            "poll_url": f"/api/v1/trader/execution/job/{job_id}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job/{job_id}", summary="Poll job status and result")
async def poll_job(
    job_id: str,
    redis=Depends(get_redis),
):
    """
    Poll the status of an enqueued analysis job.

    Returns:
    - `pending` or `processing` — job is still running
    - `done` — result available in the `report` field
    - `failed` — error message in detail
    - `404` — job not found (expired or invalid ID)
    """
    status = await get_job_status(redis, job_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    if status in ("pending", "processing"):
        return {"job_id": job_id, "status": status}

    if status == "failed":
        error = await get_job_error(redis, job_id)
        raise HTTPException(status_code=500, detail=f"Job failed: {error}")

    # status == "done"
    raw = await get_job_result(redis, job_id)
    if raw is None:
        raise HTTPException(status_code=500, detail="Result expired")

    report = AnalysisReport.model_validate_json(raw)
    return {"job_id": job_id, "status": "done", "report": report}


# --------------------------------------------------------------------------
# History endpoint — existing (unchanged)
# --------------------------------------------------------------------------

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