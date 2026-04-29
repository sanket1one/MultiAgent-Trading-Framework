"""
core/queue.py
Redis Streams queue helper for async job submission.
"""
import time
import uuid
import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Stream and consumer group constants
STREAM_NAME = "analysis:queue"
CONSUMER_GROUP = "analyst-workers"
JOB_STATUS_PREFIX = "job:status:"
JOB_RESULT_PREFIX = "job:result:"
JOB_ERROR_PREFIX = "job:error:"
JOB_TTL_SECONDS = 600  # 10 minutes


async def enqueue_job(
    redis_client: aioredis.Redis,
    ticker: str,
    session_id: Optional[str] = None,
) -> str:
    """
    Enqueue an analysis job into the Redis Stream.

    Returns:
        job_id (str): UUID for the enqueued job.
    """
    job_id = str(uuid.uuid4())
    if not session_id:
        session_id = str(uuid.uuid4())

    # Set initial status
    await redis_client.set(
        f"{JOB_STATUS_PREFIX}{job_id}", "pending", ex=JOB_TTL_SECONDS
    )

    # Add to stream
    await redis_client.xadd(
        STREAM_NAME,
        {
            "job_id": job_id,
            "ticker": ticker.upper(),
            "session_id": session_id,
            "enqueue_ts": str(int(time.time() * 1000)),
        },
    )

    logger.info(f"[Queue] Enqueued job={job_id} ticker={ticker}")
    return job_id


async def get_job_status(redis_client: aioredis.Redis, job_id: str) -> Optional[str]:
    """Get the current status of a job: pending, processing, done, or failed."""
    return await redis_client.get(f"{JOB_STATUS_PREFIX}{job_id}")


async def get_job_result(redis_client: aioredis.Redis, job_id: str) -> Optional[str]:
    """Get the JSON result of a completed job."""
    return await redis_client.get(f"{JOB_RESULT_PREFIX}{job_id}")


async def get_job_error(redis_client: aioredis.Redis, job_id: str) -> Optional[str]:
    """Get the error message for a failed job."""
    return await redis_client.get(f"{JOB_ERROR_PREFIX}{job_id}")


async def set_job_processing(redis_client: aioredis.Redis, job_id: str) -> None:
    await redis_client.set(
        f"{JOB_STATUS_PREFIX}{job_id}", "processing", ex=JOB_TTL_SECONDS
    )


async def set_job_done(
    redis_client: aioredis.Redis, job_id: str, result_json: str
) -> None:
    await redis_client.set(
        f"{JOB_RESULT_PREFIX}{job_id}", result_json, ex=JOB_TTL_SECONDS
    )
    await redis_client.set(
        f"{JOB_STATUS_PREFIX}{job_id}", "done", ex=JOB_TTL_SECONDS
    )


async def set_job_failed(
    redis_client: aioredis.Redis, job_id: str, error: str
) -> None:
    await redis_client.set(
        f"{JOB_ERROR_PREFIX}{job_id}", error, ex=JOB_TTL_SECONDS
    )
    await redis_client.set(
        f"{JOB_STATUS_PREFIX}{job_id}", "failed", ex=JOB_TTL_SECONDS
    )


async def ensure_consumer_group(redis_client: aioredis.Redis) -> None:
    """Create the consumer group if it doesn't exist. Safe to call multiple times."""
    try:
        await redis_client.xgroup_create(
            STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True
        )
        logger.info(f"[Queue] Created consumer group '{CONSUMER_GROUP}'")
    except Exception:
        # Group already exists
        pass
