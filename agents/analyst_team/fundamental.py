"""
agents/analyst_team/fundamental.py
FundamentalAgent — analyses P/E, EPS, revenue growth, margins, and debt ratios.
"""
from typing import Any, Dict

import redis.asyncio as aioredis

from agents.analyst_team.base import BaseAnalystAgent
from models.analyst import AnalysisResult, SignalType
from core.tools import fetch_fundamental_data


class FundamentalAgent(BaseAnalystAgent):
    """
    Analyses fundamental financial ratios fetched via yfinance.

    Signal heuristic (stub):
      BUY  — low P/E (<20), positive EPS, healthy margins (>20%), low D/E (<1)
      SELL — high P/E (>35) or negative EPS or very high D/E (>3)
      HOLD — everything else
    """

    agent_type = "fundamental"

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__(redis_client)

    async def _fetch_data(self, ticker: str) -> Dict[str, Any]:
        return await fetch_fundamental_data(ticker)

    def _build_prompt(self, data: Dict[str, Any]) -> str:
        return (
            f"You are a fundamental analysis expert. Analyse the following financial "
            f"metrics for {data.get('ticker', 'the stock')} and return a JSON object "
            f"with keys: signal (BUY/SELL/HOLD), confidence (0.0–1.0), reasoning.\n\n"
            f"Metrics:\n"
            f"- Trailing P/E Ratio : {data.get('pe_ratio')}\n"
            f"- Forward P/E Ratio  : {data.get('forward_pe')}\n"
            f"- EPS (TTM)          : {data.get('eps')}\n"
            f"- Revenue Growth     : {data.get('revenue_growth')}\n"
            f"- Gross Margins      : {data.get('gross_margins')}\n"
            f"- Debt/Equity        : {data.get('debt_to_equity')}\n"
            f"- Current Ratio      : {data.get('current_ratio')}\n"
            f"- Return on Equity   : {data.get('return_on_equity')}\n"
            f"- Market Cap         : {data.get('market_cap')}\n"
            f"- Sector             : {data.get('sector')}\n\n"
            f"Respond ONLY with valid JSON."
        )

    def _rule_based_signal(self, data: Dict[str, Any]) -> tuple[SignalType, float]:
        pe = data.get("pe_ratio")
        eps = data.get("eps")
        margins = data.get("gross_margins") or 0.0
        de = data.get("debt_to_equity") or 0.0

        if pe is None:
            return "HOLD", 0.4

        if pe < 20 and (eps or 0) > 0 and margins > 0.20 and de < 1.0:
            return "BUY", 0.75
        if pe > 35 or (eps is not None and eps < 0) or de > 3.0:
            return "SELL", 0.65

        return "HOLD", 0.5
