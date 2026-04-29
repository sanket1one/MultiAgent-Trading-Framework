"""
agents/analyst_team/technical.py
TechnicalAgent — analyses RSI, MACD, and moving average crossovers.
"""
from typing import Any, Dict

import redis.asyncio as aioredis

from agents.analyst_team.base import BaseAnalystAgent
from models.analyst import AnalysisResult, SignalType
from core.tools import fetch_technical_indicators


class TechnicalAgent(BaseAnalystAgent):
    """
    Analyses price-based technical indicators from yfinance + ta library.

    Signal heuristic (stub):
      BUY  — RSI < 40 (oversold) AND MACD > Signal AND price > SMA50
      SELL — RSI > 65 (overbought) OR MACD < Signal AND price < SMA50
      HOLD — everything else
    """

    agent_type = "technical"

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__(redis_client)

    async def _fetch_data(self, ticker: str) -> Dict[str, Any]:
        return await fetch_technical_indicators(ticker)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        return (
            f"You are a technical analysis expert. Analyse the following indicators "
            f"for {data.get('ticker', 'the stock')} and return a JSON object with keys: "
            f"signal (BUY/SELL/HOLD), confidence (0.0–1.0), reasoning.\n\n"
            f"Indicators:\n"
            f"- RSI (14-day)       : {data.get('rsi')}\n"
            f"- MACD               : {data.get('macd')}\n"
            f"- MACD Signal Line   : {data.get('macd_signal')}\n"
            f"- SMA 50-day         : {data.get('sma_50')}\n"
            f"- SMA 200-day        : {data.get('sma_200')}\n"
            f"- Latest Close Price : {data.get('close_price')}\n"
            f"- Data Period        : {data.get('period')}\n\n"
            f"Respond ONLY with valid JSON."
        )

    def _rule_based_signal(self, data: Dict[str, Any]) -> tuple[SignalType, float]:
        rsi = data.get("rsi")
        macd = data.get("macd") or 0.0
        macd_signal = data.get("macd_signal") or 0.0
        close = data.get("close_price") or 0.0
        sma50 = data.get("sma_50") or close

        if rsi is None:
            return "HOLD", 0.4

        bullish_macd = macd > macd_signal
        above_sma50 = close > sma50

        if rsi < 40 and bullish_macd and above_sma50:
            return "BUY", 0.72
        if rsi > 65 and (not bullish_macd or not above_sma50):
            return "SELL", 0.68

        return "HOLD", 0.5
