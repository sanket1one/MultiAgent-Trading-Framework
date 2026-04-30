"""
scripts/benchmark.py
Benchmarking script for MultiAgent Trading Framework.
Measures latency (P50, P95, P99), throughput (RPS), and success rate.
"""
import asyncio
import time
import argparse
import statistics
from typing import List, Dict, Any

import httpx
from pydantic import BaseModel

# Configuration
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX"]


class BenchResult(BaseModel):
    latency: float
    status_code: int
    ticker: str
    success: bool


async def run_request(client: httpx.AsyncClient, base_url: str, ticker: str) -> BenchResult:
    start_time = time.perf_counter()
    success = False
    status_code = 0
    try:
        response = await client.post(
            f"{base_url}/api/v1/trader/execution/analyze",
            json={"ticker": ticker},
            timeout=30.0
        )
        status_code = response.status_code
        if status_code == 200:
            success = True
    except Exception as e:
        print(f"Request failed for {ticker}: {e}")
        status_code = 500

    latency = (time.perf_counter() - start_time) * 1000
    return BenchResult(latency=latency, status_code=status_code, ticker=ticker, success=success)


async def benchmark(
    num_requests: int,
    concurrency: int,
    base_url: str,
    tickers: List[str]
):
    print(f"\n🚀 Starting Benchmark")
    print(f"-------------------------------")
    print(f"Total Requests: {num_requests}")
    print(f"Concurrency:    {concurrency}")
    print(f"Target URL:     {base_url}")
    print(f"-------------------------------\n")

    results: List[BenchResult] = []
    
    # Simple semaphore to limit concurrency
    semaphore = asyncio.Semaphore(concurrency)

    async def sem_run(ticker: str):
        async with semaphore:
            return await run_request(client, base_url, ticker)

    start_bench = time.perf_counter()
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for i in range(num_requests):
            ticker = tickers[i % len(tickers)]
            tasks.append(sem_run(ticker))
        
        results = await asyncio.gather(*tasks)

    end_bench = time.perf_counter()
    total_time = end_bench - start_bench

    # Calculate statistics
    latencies = sorted([r.latency for r in results])
    success_count = sum(1 for r in results if r.success)
    error_count = num_requests - success_count
    
    if not latencies:
        print("No results to report.")
        return

    avg_latency = statistics.mean(latencies)
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    rps = num_requests / total_time

    print(f"📊 Benchmark Results")
    print(f"-------------------------------")
    print(f"Total Time:         {total_time:.2f}s")
    print(f"Throughput (RPS):   {rps:.2f} req/s")
    print(f"Success Rate:       {(success_count/num_requests)*100:.1f}% ({success_count}/{num_requests})")
    print(f"Errors:             {error_count}")
    print(f"-------------------------------")
    print(f"Min Latency:        {min(latencies):.1f}ms")
    print(f"Avg Latency:        {avg_latency:.1f}ms")
    print(f"P50 (Median):       {p50:.1f}ms")
    print(f"P95 Latency:        {p95:.1f}ms  <-- target ≤2800ms")
    print(f"P99 Latency:        {p99:.1f}ms")
    print(f"Max Latency:        {max(latencies):.1f}ms")
    print(f"-------------------------------\n")

    if p95 <= 2800:
        print("✅ SUCCESS: P95 is within the 2.8s target.")
    else:
        print("❌ FAILURE: P95 exceeds the 2.8s target.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MultiAgent Framework Benchmark")
    parser.add_argument("--requests", type=int, default=10, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of concurrent requests")
    parser.add_argument("--url", type=str, default=DEFAULT_BASE_URL, help="Base URL of the API")
    
    args = parser.parse_args()
    
    asyncio.run(benchmark(
        num_requests=args.requests,
        concurrency=args.concurrency,
        base_url=args.url,
        tickers=DEFAULT_TICKERS
    ))
