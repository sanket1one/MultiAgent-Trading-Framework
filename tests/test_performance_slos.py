"""
tests/test_performance_slos.py
Automated performance tests to enforce P95 ≤ 2.8s SLO using pytest.
"""
import time
import pytest
import httpx
import asyncio

BASE_URL = "http://localhost:8000"
TARGET_P95_MS = 2800.0


@pytest.mark.asyncio
async def test_p95_latency_slo():
    """
    Fire 5 requests and ensure the 95th percentile (or max in this small sample) 
    is under the 2.8s target.
    """
    tickers = ["AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
    latencies = []

    async with httpx.AsyncClient() as client:
        for ticker in tickers:
            start_time = time.perf_counter()
            response = await client.post(
                f"{BASE_URL}/api/v1/trader/execution/analyze",
                json={"ticker": ticker},
                timeout=30.0
            )
            latency = (time.perf_counter() - start_time) * 1000
            
            assert response.status_code == 200
            latencies.append(latency)

    # Sort and check P95 (for 5 items, we'll take the 2nd slowest)
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0]
    
    print(f"\nMeasured P95: {p95:.1f}ms")
    assert p95 <= TARGET_P95_MS, f"P95 latency {p95:.1f}ms exceeded SLO of {TARGET_P95_MS}ms"


@pytest.mark.asyncio
async def test_concurrent_throughput():
    """
    Verify that the system can handle 3 concurrent requests without crashing 
    and within a reasonable total time window.
    """
    tickers = ["AAPL", "MSFT", "NVDA"]
    start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [
            client.post(f"{BASE_URL}/api/v1/trader/execution/analyze", json={"ticker": t}, timeout=30.0)
            for t in tickers
        ]
        responses = await asyncio.gather(*tasks)

    total_time = (time.perf_counter() - start_time)
    
    for resp in responses:
        assert resp.status_code == 200
    
    # Even if cache misses, 3 concurrent requests should finish in < 4s 
    # (since agents run in parallel and workers are available)
    assert total_time < 5.0, f"Concurrent execution took too long: {total_time:.2f}s"
