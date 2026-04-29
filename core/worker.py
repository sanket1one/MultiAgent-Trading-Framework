"""
core/worker.py
Background worker that consumes jobs from the Redis Stream
and runs the ReActOrchestrator for each one.
"""
import asyncio
import time
import logging

import redis.asyncio as aioredis

from agents.orchestrator import ReActOrchestrator
from core.queue import (
    STREAM_NAME,
    CONSUMER_GROUP,
    ensure_consumer_group,
    set_job_processing,
    set_job_done,
    set_job_failed,
)

logger = logging.getLogger(__name__)

# Trim the stream every N messages processed
_TRIM_INTERVAL = 100
_STREAM_MAX_LEN = 10_000


async def analysis_worker(
    worker_id: int,
    redis_client: aioredis.Redis,
    shutdown_event: asyncio.Event,
) -> None:
    """
    Background worker loop.

    Reads one job at a time from the Redis Stream, runs the orchestrator,
    stores the result back in Redis, writes to MongoDB, and ACKs.
    """
    consumer = f"worker-{worker_id}"
    processed = 0

    # Ensure the consumer group exists
    await ensure_consumer_group(redis_client)

    logger.info(f"[Worker-{worker_id}] Started — listening on '{STREAM_NAME}'")

    while not shutdown_event.is_set():
        try:
            # Block-read one message (1s timeout so we can check shutdown)
            messages = await redis_client.xreadgroup(
                CONSUMER_GROUP,
                consumer,
                {STREAM_NAME: ">"},
                count=1,
                block=1000,
            )

            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, data in entries:
                    job_id = data["job_id"]
                    ticker = data["ticker"]
                    session_id = data["session_id"]
                    enqueue_ts = int(data.get("enqueue_ts", 0))

                    t_pickup = time.time()
                    queue_wait_ms = (t_pickup * 1000 - enqueue_ts) if enqueue_ts else 0

                    logger.info(
                        f"[Worker-{worker_id}] Picked up job={job_id} "
                        f"ticker={ticker} queue_wait={queue_wait_ms:.0f}ms"
                    )

                    # Mark as processing
                    await set_job_processing(redis_client, job_id)

                    try:
                        # Run the full orchestrator
                        orchestrator = ReActOrchestrator(redis_client=redis_client)
                        report = await orchestrator.run(ticker, session_id)

                        # Store result for client polling
                        await set_job_done(
                            redis_client, job_id, report.model_dump_json()
                        )

                        t_done = time.time()
                        total_ms = (t_done * 1000 - enqueue_ts) if enqueue_ts else 0
                        logger.info(
                            f"[Worker-{worker_id}] Completed job={job_id} "
                            f"ticker={ticker} signal={report.final_signal} "
                            f"total={total_ms:.0f}ms"
                        )

                        # SLO check
                        if total_ms > 2800:
                            logger.warning(
                                f"[SLO BREACH] job={job_id} took {total_ms:.0f}ms (>2800ms)"
                            )

                    except Exception as e:
                        logger.error(
                            f"[Worker-{worker_id}] Failed job={job_id}: {e}"
                        )
                        await set_job_failed(redis_client, job_id, str(e))

                    # Acknowledge the message
                    await redis_client.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)

                    # Periodic stream trim
                    processed += 1
                    if processed % _TRIM_INTERVAL == 0:
                        await redis_client.xtrim(
                            STREAM_NAME, maxlen=_STREAM_MAX_LEN, approximate=True
                        )

        except asyncio.CancelledError:
            logger.info(f"[Worker-{worker_id}] Cancelled — shutting down")
            break
        except Exception as e:
            logger.error(f"[Worker-{worker_id}] Unexpected error: {e}")
            await asyncio.sleep(1)

    logger.info(f"[Worker-{worker_id}] Stopped")
