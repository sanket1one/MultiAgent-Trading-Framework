"""
agents/analyst_team/news.py
NewsAgent — analyses recent company news headlines from Finnhub.
"""
from typing import Any, Dict

import redis.asyncio as aioredis

from agents.analyst_team.base import BaseAnalystAgent
from models.analyst import AnalysisResult, SignalType
from core.tools import fetch_news_headlines

# Simple keyword lists for the rule-based stub
_BULLISH_KEYWORDS = {
    "beat", "record", "growth", "profit", "upgrade", "buy", "raised",
    "expansion", "launch", "innovative", "strong", "rally", "surge",
}
_BEARISH_KEYWORDS = {
    "miss", "loss", "downgrade", "sell", "cut", "decline", "layoff",
    "lawsuit", "recall", "fraud", "investigation", "crash", "drop",
}


class NewsAgent(BaseAnalystAgent):
    """
    Analyses recent company news via Finnhub.

    Signal heuristic (stub):
      Counts bullish / bearish keywords across all headlines.
      BUY  — bullish keywords > bearish by a margin of 2+
      SELL — bearish keywords > bullish by a margin of 2+
      HOLD — roughly equal or too few headlines
    """

    agent_type = "news"

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__(redis_client)

    async def _fetch_data(self, ticker: str) -> Dict[str, Any]:
        return await fetch_news_headlines(ticker, limit=10)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        headlines_text = "\n".join(
            f"  [{i+1}] {h['headline']}"
            for i, h in enumerate(data.get("headlines", []))
        ) or "  No headlines available."

        return (
            f"You are a financial news analyst. Analyse the following recent headlines "
            f"for {data.get('ticker', 'the stock')} and return a JSON object with keys: "
            f"signal (BUY/SELL/HOLD), confidence (0.0–1.0), reasoning.\n\n"
            f"Recent Headlines ({data.get('headline_count', 0)} total):\n"
            f"{headlines_text}\n\n"
            f"Respond ONLY with valid JSON."
        )

    def _rule_based_signal(self, data: Dict[str, Any]) -> tuple[SignalType, float]:
        if "error" in data or not data.get("headlines"):
            return "HOLD", 0.3

        bullish_count = 0
        bearish_count = 0

        for item in data.get("headlines", []):
            text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
            bullish_count += sum(1 for kw in _BULLISH_KEYWORDS if kw in text)
            bearish_count += sum(1 for kw in _BEARISH_KEYWORDS if kw in text)

        total = bullish_count + bearish_count
        if total == 0:
            return "HOLD", 0.4

        if bullish_count - bearish_count >= 2:
            confidence = round(min(bullish_count / total, 0.85), 2)
            return "BUY", confidence
        if bearish_count - bullish_count >= 2:
            confidence = round(min(bearish_count / total, 0.85), 2)
            return "SELL", confidence

        return "HOLD", 0.5
