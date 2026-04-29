"""
agents/orchestrator.py
ReActOrchestrator — runs all 4 analyst agents concurrently for a ticker,
aggregates their signals via weighted majority vote, and persists the
AnalysisReport to MongoDB via ChatRepository.
"""
import asyncio
import json
import logging
import uuid
from collections import Counter
from typing import List, Optional

import redis.asyncio as aioredis

from agents.analyst_team.base import BaseAnalystAgent
from agents.analyst_team.fundamental import FundamentalAgent
from models.analyst import AnalysisReport, AnalysisResult, SignalType
from agents.analyst_team.news import NewsAgent
from agents.analyst_team.sentiment import SentimentAgent
from agents.analyst_team.technical import TechnicalAgent
from core.chat_repository import ChatRepository

logger = logging.getLogger(__name__)

# Confidence-based weights per agent type (tune these)
_AGENT_WEIGHTS: dict[str, float] = {
    "fundamental": 1.2,
    "technical": 1.0,
    "sentiment": 0.8,
    "news": 0.7,
}


class ReActOrchestrator:
    """
    Coordinates the 4-agent analyst team using a ReAct-style loop.

    Each agent independently:
      Thought → Action (fetch + analyse) → Observation (AnalysisResult)

    The orchestrator then:
      1. Runs all agents concurrently via asyncio.gather
      2. Aggregates signals using a confidence-weighted majority vote
      3. Persists the AnalysisReport to MongoDB
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis_client = redis_client
        self.agents: List[BaseAnalystAgent] = [
            FundamentalAgent(redis_client),
            TechnicalAgent(redis_client),
            SentimentAgent(redis_client),
            NewsAgent(redis_client),
        ]
        self.chat_repo = ChatRepository()

    async def run(
        self, ticker: str, session_id: Optional[str] = None
    ) -> AnalysisReport:
        """
        Full orchestration pipeline for a single ticker.

        Args:
            ticker:     Stock symbol (e.g. "AAPL")
            session_id: Optional session ID for MongoDB history grouping

        Returns:
            AnalysisReport with aggregated signal and all agent results
        """
        ticker = ticker.upper()
        if not session_id:
            session_id = str(uuid.uuid4())

        logger.info(
            f"[Orchestrator] Starting analysis for {ticker} | session={session_id}"
        )

        # --- ReAct: run all agents concurrently (Thought + Action in parallel) ---
        results: List[AnalysisResult] = await asyncio.gather(
            *[self._react_loop(agent, ticker) for agent in self.agents],
            return_exceptions=False,
        )

        # --- Observation: aggregate ---
        report = self._aggregate(ticker, session_id, results)

        # --- Persist to MongoDB ---
        await self._save_to_history(session_id, report)

        logger.info(
            f"[Orchestrator] Done — {ticker} → {report.final_signal} "
            f"({report.aggregate_confidence:.2f})"
        )
        return report

    # ------------------------------------------------------------------
    # Per-agent ReAct Loop
    # ------------------------------------------------------------------

    async def _react_loop(
        self, agent: BaseAnalystAgent, ticker: str
    ) -> AnalysisResult:
        """
        One iteration of the ReAct loop for a single agent:
          Thought  → "I need to analyse {ticker} from a {agent_type} perspective"
          Action   → agent.analyze(ticker) calls fetch + LLM
          Observe  → return validated AnalysisResult
        """
        thought = (
            f"[Thought] I need to analyse {ticker} from a "
            f"{agent.agent_type} perspective."
        )
        logger.debug(thought)

        try:
            result = await agent.analyze(ticker)
            logger.debug(
                f"[Observe] {agent.agent_type} → {result.signal} ({result.confidence:.2f})"
            )
            return result
        except Exception as e:
            logger.error(f"[Orchestrator] {agent.agent_type} agent failed: {e}")
            # Return a neutral result on failure so we don't crash the pipeline
            return AnalysisResult(
                ticker=ticker,
                agent_type=agent.agent_type,  # type: ignore[arg-type]
                signal="HOLD",
                confidence=0.0,
                reasoning=f"Agent failed with error: {e}",
                raw_data={},
            )

    # ------------------------------------------------------------------
    # Aggregation — Weighted Majority Vote
    # ------------------------------------------------------------------

    def _aggregate(
        self, ticker: str, session_id: str, results: List[AnalysisResult]
    ) -> AnalysisReport:
        """
        Confidence-weighted majority vote across all agent signals.

        For each agent result:
          weighted_score[signal] += confidence * agent_weight

        Final signal = argmax(weighted_score)
        Aggregate confidence = winning_score / total_weight
        """
        weighted_scores: dict[str, float] = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        total_weight = 0.0

        for result in results:
            weight = _AGENT_WEIGHTS.get(result.agent_type, 1.0)
            weighted_scores[result.signal] += result.confidence * weight
            total_weight += weight

        final_signal: SignalType = max(weighted_scores, key=weighted_scores.get)  # type: ignore
        winning_score = weighted_scores[final_signal]
        aggregate_confidence = round(winning_score / total_weight, 4) if total_weight else 0.0

        votes = Counter(r.signal for r in results)
        summary = (
            f"Weighted majority vote: BUY={weighted_scores['BUY']:.2f}, "
            f"SELL={weighted_scores['SELL']:.2f}, HOLD={weighted_scores['HOLD']:.2f}. "
            f"Raw vote counts: {dict(votes)}. "
            f"Final: {final_signal} with aggregate confidence {aggregate_confidence:.2%}."
        )

        return AnalysisReport(
            ticker=ticker,
            session_id=session_id,
            final_signal=final_signal,
            aggregate_confidence=aggregate_confidence,
            agent_results=results,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # MongoDB Persistence
    # ------------------------------------------------------------------

    async def _save_to_history(
        self, session_id: str, report: AnalysisReport
    ) -> None:
        """Persist the AnalysisReport as a structured message in MongoDB."""
        try:
            await self.chat_repo.save_message(
                session_id=session_id,
                role="orchestrator",
                content=report.model_dump_json(),
            )
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to persist report to MongoDB: {e}")
