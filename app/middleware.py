"""
app/middleware.py
Latency tracking middleware — logs P95-relevant timing for every request
and warns on SLO breach (>2800ms).
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("latency")


class LatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - t0) * 1000

        logger.info(
            f"method={request.method} path={request.url.path} "
            f"status={response.status_code} latency_ms={latency_ms:.1f}"
        )

        if latency_ms > 2800:
            logger.warning(
                f"SLO BREACH: {request.url.path} took {latency_ms:.1f}ms (>2800ms)"
            )

        return response
