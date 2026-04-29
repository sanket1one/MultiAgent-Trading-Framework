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
        # yfinance often returns MultiIndex columns now; we flatten them if present
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        
        if df.empty:
            return {"ticker": ticker, "error": "No OHLCV data returned"}

        # Flatten MultiIndex columns if they exist (e.g., [('Close', 'AAPL')] -> 'Close')
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure we have the required columns
        required = ["Close"]
        for col in required:
            if col not in df.columns:
                return {"ticker": ticker, "error": f"Missing required column: {col}"}

        close = df["Close"]
        
        # Compute indicators using 'ta' library
        try:
            df["RSI"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()
            macd_obj = ta.trend.MACD(close=close)
            df["MACD"] = macd_obj.macd()
            df["MACD_Signal"] = macd_obj.macd_signal()
            df["SMA_50"] = ta.trend.SMAIndicator(close=close, window=50).sma_indicator()
            df["SMA_200"] = ta.trend.SMAIndicator(close=close, window=200).sma_indicator()
        except Exception as e:
            logger.error(f"[TechnicalTool] Indicator computation failed for {ticker}: {e}")

        latest = df.iloc[-1]
        
        # Convert to float and round carefully
        def get_val(series_val, decimals=2):
            try:
                v = float(series_val)
                return round(v, decimals) if pd.notna(v) else None
            except (TypeError, ValueError):
                return None

        return {
            "ticker": ticker,
            "rsi": get_val(latest.get("RSI"), 2),
            "macd": get_val(latest.get("MACD"), 4),
            "macd_signal": get_val(latest.get("MACD_Signal"), 4),
            "sma_50": get_val(latest.get("SMA_50"), 2),
            "sma_200": get_val(latest.get("SMA_200"), 2),
            "close_price": get_val(latest.get("Close"), 2),
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
        # Use a more recent range to avoid 403 on older data if applicable, 
        # but usually 403 means the endpoint is restricted.
        try:
            data = client.stock_social_sentiment(ticker)
            reddit = data.get("reddit", [])
            twitter = data.get("twitter", [])
        except Exception as e:
            # Re-raise to be caught by the outer try-except
            raise e

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
        # Use a more reasonable date range (last 30 days)
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        news_items = client.company_news(ticker, _from=start_date, to=end_date)
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
