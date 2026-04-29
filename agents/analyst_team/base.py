"""
agents/analyst_team/base.py
Abstract base class for all analyst agents.
Implements the Template Method pattern:
  analyze() = check cache → fetch data → build prompt → call LLM → return validated result
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from models.analyst import AnalysisResult, SignalType

logger = logging.getLogger(__name__)

# Default Redis TTL for cached analysis results (5 minutes)
DEFAULT_CACHE_TTL_SECONDS = 300


class BaseAnalystAgent(ABC):
    """
    Abstract base for all analyst agents.

    Subclasses must implement:
      - agent_type: str class attribute
      - _fetch_data(ticker) -> Dict
      - _build_prompt(data) -> str
    """

    agent_type: str  # e.g. "fundamental", "technical", "sentiment", "news"

    def __init__(self, redis_client: aioredis.Redis):
        self.redis_client = redis_client

    # ------------------------------------------------------------------
    # Public Template Method
    # ------------------------------------------------------------------

    async def analyze(self, ticker: str) -> AnalysisResult:
        """
        Full ReAct-style analysis pipeline for a single ticker.

        Steps:
          1. Thought  — check if a cached result is still valid
          2. Action   — fetch fresh data if cache miss
          3. Thought  — build LLM prompt from the data
          4. Action   — call LLM (or rule-based stub)
          5. Observe  — validate and return AnalysisResult
        """
        ticker = ticker.upper()
        cache_key = self._cache_key(ticker)

        # --- Step 1: Check cache ---
        cached = await self._get_cached(cache_key)
        if cached:
            logger.info(f"[{self.agent_type}] Cache HIT for {ticker}")
            return cached

        logger.info(f"[{self.agent_type}] Cache MISS — fetching data for {ticker}")

        # --- Step 2: Fetch raw data ---
        raw_data = await self._fetch_data(ticker)

        # --- Step 3: Build prompt ---
        prompt = self._build_prompt(raw_data)

        # --- Step 4: Call LLM (or stub) ---
        signal, confidence, reasoning = await self._call_llm(prompt, raw_data)

        # --- Step 5: Validate and cache ---
        result = AnalysisResult(
            ticker=ticker,
            agent_type=self.agent_type,  # type: ignore[arg-type]
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            raw_data=raw_data,
        )
        await self._set_cache(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Abstract Methods — Subclasses implement these
    # ------------------------------------------------------------------

    @abstractmethod
    async def _fetch_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch raw data from the appropriate data source."""
        ...

    @abstractmethod
    def _build_prompt(self, data: Dict[str, Any]) -> str:
        """Build a structured LLM prompt from the fetched data."""
        ...

    # ------------------------------------------------------------------
    # LLM Call — swap this for your real provider (OpenAI, Gemini, etc.)
    # ------------------------------------------------------------------

    async def _call_llm(
        self, prompt: str, raw_data: Dict[str, Any]
    ) -> tuple[SignalType, float, str]:
        """
        Send the prompt to an LLM and parse the structured response.

        ⚠️  STUB IMPLEMENTATION — replace the body below with your real
        LLM API call, e.g.:
            import google.generativeai as genai
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model)
            resp = await model.generate_content_async(...)

        The LLM should respond in JSON:
        {
          "signal": "BUY" | "SELL" | "HOLD",
          "confidence": 0.0–1.0,
          "reasoning": "<step-by-step explanation>"
        }
        """
        signal, confidence = self._rule_based_signal(raw_data)
        reasoning = (
            f"[STUB] {self.agent_type.capitalize()} agent rule-based analysis.\n"
            f"Prompt sent to LLM:\n{prompt}\n\n"
            f"Derived signal: {signal} with confidence {confidence:.2f}."
        )
        return signal, confidence, reasoning

    # ------------------------------------------------------------------
    # Redis Cache Helpers
    # ------------------------------------------------------------------

    def _cache_key(self, ticker: str) -> str:
        return f"analysis:{self.agent_type}:{ticker}"

    async def _get_cached(self, key: str) -> Optional[AnalysisResult]:
        try:
            raw = await self.redis_client.get(key)
            if raw:
                return AnalysisResult.model_validate_json(raw)
        except Exception as e:
            logger.warning(f"[{self.agent_type}] Redis GET failed: {e}")
        return None

    async def _set_cache(
        self, key: str, result: AnalysisResult, ttl: int = DEFAULT_CACHE_TTL_SECONDS
    ) -> None:
        try:
            await self.redis_client.set(key, result.model_dump_json(), ex=ttl)
        except Exception as e:
            logger.warning(f"[{self.agent_type}] Redis SET failed: {e}")

    # ------------------------------------------------------------------
    # Rule-based signal stub (used when LLM is not configured)
    # ------------------------------------------------------------------

    def _rule_based_signal(
        self, data: Dict[str, Any]
    ) -> tuple[SignalType, float]:
        """
        Lightweight heuristic fallback so the system runs without API keys.
        Subclasses can override for agent-specific logic.
        """
        return "HOLD", 0.5
