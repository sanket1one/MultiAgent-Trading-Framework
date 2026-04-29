"""
agents/analyst_team/sentiment.py
SentimentAgent — analyses social media bullish/bearish scores from Finnhub.
"""
from typing import Any, Dict

import redis.asyncio as aioredis

from agents.analyst_team.base import BaseAnalystAgent
from models.analyst import AnalysisResult, SignalType
from core.tools import fetch_sentiment_data


class SentimentAgent(BaseAnalystAgent):
    """
    Analyses social media sentiment (Reddit + Twitter) via Finnhub.

    Signal heuristic (stub):
      BUY  — avg bullish score > 60% and mention count > 5
      SELL — avg bearish score > 60% and mention count > 5
      HOLD — neutral or insufficient data
    """

    agent_type = "sentiment"

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__(redis_client)

    async def _fetch_data(self, ticker: str) -> Dict[str, Any]:
        return await fetch_sentiment_data(ticker)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        return (
            f"You are a market sentiment analyst. Analyse the following social media "
            f"sentiment data for {data.get('ticker', 'the stock')} and return a JSON "
            f"object with keys: signal (BUY/SELL/HOLD), confidence (0.0–1.0), reasoning.\n\n"
            f"Sentiment Data:\n"
            f"- Reddit Bullish %      : {data.get('reddit_bullish_score')}\n"
            f"- Reddit Bearish %      : {data.get('reddit_bearish_score')}\n"
            f"- Reddit Mentions       : {data.get('reddit_mention_count')}\n"
            f"- Twitter Bullish %     : {data.get('twitter_bullish_score')}\n"
            f"- Twitter Bearish %     : {data.get('twitter_bearish_score')}\n"
            f"- Twitter Mentions      : {data.get('twitter_mention_count')}\n\n"
            f"Respond ONLY with valid JSON."
        )

    def _rule_based_signal(self, data: Dict[str, Any]) -> tuple[SignalType, float]:
        bullish = (
            (data.get("reddit_bullish_score") or 0.0)
            + (data.get("twitter_bullish_score") or 0.0)
        ) / 2.0
        bearish = (
            (data.get("reddit_bearish_score") or 0.0)
            + (data.get("twitter_bearish_score") or 0.0)
        ) / 2.0
        mentions = (
            (data.get("reddit_mention_count") or 0)
            + (data.get("twitter_mention_count") or 0)
        )

        if "error" in data:
            return "HOLD", 0.3

        if bullish > 0.60 and mentions >= 5:
            return "BUY", round(min(bullish, 0.90), 2)
        if bearish > 0.60 and mentions >= 5:
            return "SELL", round(min(bearish, 0.90), 2)

        return "HOLD", 0.5
