"""
core/tools.py
Async data-fetching utilities used by the analyst agents.
Each function returns a clean Dict that agents pass to _build_prompt().
"""
import asyncio
import logging
from typing import Any, Dict, List

import finnhub
import pandas as pd
import ta
import yfinance as yf

from core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fundamental Data  (yfinance)
# ---------------------------------------------------------------------------

async def fetch_fundamental_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch key fundamental ratios for a ticker via yfinance.
    Runs the blocking yfinance call in a thread-pool executor.
    """
    def _fetch() -> Dict[str, Any]:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return {
            "ticker": ticker,
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margins": info.get("grossMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "return_on_equity": info.get("returnOnEquity"),
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
        }

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.error(f"[FundamentalTool] Failed to fetch data for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


# ---------------------------------------------------------------------------
# Technical Indicators  (yfinance + ta)
# ---------------------------------------------------------------------------

async def fetch_technical_indicators(ticker: str, period: str = "3mo") -> Dict[str, Any]:
    """
    Fetch OHLCV history for `period` and compute RSI, MACD, and SMA indicators.
    """
    def _fetch() -> Dict[str, Any]:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        if df.empty:
            return {"ticker": ticker, "error": "No OHLCV data returned"}

        close = df["Close"].squeeze()
        df["RSI"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()
        macd_obj = ta.trend.MACD(close=close)
        df["MACD"] = macd_obj.macd()
        df["MACD_Signal"] = macd_obj.macd_signal()
        df["SMA_50"] = ta.trend.SMAIndicator(close=close, window=50).sma_indicator()
        df["SMA_200"] = ta.trend.SMAIndicator(close=close, window=200).sma_indicator()

        latest = df.iloc[-1]
        return {
            "ticker": ticker,
            "rsi": round(float(latest["RSI"]), 2) if pd.notna(latest["RSI"]) else None,
            "macd": round(float(latest["MACD"]), 4) if pd.notna(latest["MACD"]) else None,
            "macd_signal": round(float(latest["MACD_Signal"]), 4) if pd.notna(latest["MACD_Signal"]) else None,
            "sma_50": round(float(latest["SMA_50"]), 2) if pd.notna(latest["SMA_50"]) else None,
            "sma_200": round(float(latest["SMA_200"]), 2) if pd.notna(latest["SMA_200"]) else None,
            "close_price": round(float(latest["Close"]), 2),
            "period": period,
        }

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.error(f"[TechnicalTool] Failed to fetch indicators for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


# ---------------------------------------------------------------------------
# Social Sentiment  (Finnhub)
# ---------------------------------------------------------------------------

async def fetch_sentiment_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch social-media sentiment scores for the ticker from Finnhub.
    Returns bullish/bearish scores and a calculated net sentiment.
    """
    def _fetch() -> Dict[str, Any]:
        client = finnhub.Client(api_key=settings.finnhub_api_key)
        data = client.stock_social_sentiment(ticker, _from="2024-01-01", to="2025-12-31")
        reddit = data.get("reddit", [])
        twitter = data.get("twitter", [])

        def avg(items: list, key: str) -> float:
            vals = [i[key] for i in items if key in i]
            return round(sum(vals) / len(vals), 4) if vals else 0.0

        return {
            "ticker": ticker,
            "reddit_bullish_score": avg(reddit, "bullishPercent"),
            "reddit_bearish_score": avg(reddit, "bearishPercent"),
            "twitter_bullish_score": avg(twitter, "bullishPercent"),
            "twitter_bearish_score": avg(twitter, "bearishPercent"),
            "reddit_mention_count": len(reddit),
            "twitter_mention_count": len(twitter),
        }

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.warning(f"[SentimentTool] Finnhub sentiment failed for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}


# ---------------------------------------------------------------------------
# News Headlines  (Finnhub)
# ---------------------------------------------------------------------------

async def fetch_news_headlines(ticker: str, limit: int = 10) -> Dict[str, Any]:
    """
    Fetch recent company news headlines from Finnhub.
    Returns a list of headline strings and their sentiment (if available).
    """
    def _fetch() -> Dict[str, Any]:
        client = finnhub.Client(api_key=settings.finnhub_api_key)
        news_items = client.company_news(ticker, _from="2025-01-01", to="2025-12-31")
        headlines = [
            {
                "headline": item.get("headline", ""),
                "summary": item.get("summary", "")[:200],
                "source": item.get("source", ""),
                "datetime": item.get("datetime", 0),
            }
            for item in (news_items or [])[:limit]
        ]
        return {
            "ticker": ticker,
            "headline_count": len(headlines),
            "headlines": headlines,
        }

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch)
    except Exception as e:
        logger.warning(f"[NewsTool] Finnhub news failed for {ticker}: {e}")
        return {"ticker": ticker, "error": str(e)}
