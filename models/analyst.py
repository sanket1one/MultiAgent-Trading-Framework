"""
models/analyst.py
Pydantic domain models for the Analyst Team.
Used by agents, the orchestrator, and all API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timezone
import uuid


SignalType = Literal["BUY", "SELL", "HOLD"]


class AnalysisRequest(BaseModel):
    """Input model for triggering an analysis on a given ticker."""
    ticker: str = Field(..., description="Stock ticker symbol, e.g. AAPL", min_length=1, max_length=10)
    session_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Session ID for tracking conversation / analysis history in MongoDB"
    )


class AnalysisResult(BaseModel):
    """Output model for a single agent's analysis of one ticker."""
    ticker: str
    agent_type: Literal["fundamental", "technical", "sentiment", "news"]
    signal: SignalType = Field(..., description="Trading signal: BUY, SELL, or HOLD")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reasoning: str = Field(..., description="Agent's step-by-step ReAct reasoning")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw data fetched for this analysis")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AnalysisReport(BaseModel):
    """Aggregated report produced by the ReActOrchestrator across all 4 agents."""
    ticker: str
    session_id: str
    final_signal: SignalType = Field(..., description="Aggregated signal via weighted majority vote")
    aggregate_confidence: float = Field(..., ge=0.0, le=1.0)
    agent_results: List[AnalysisResult] = Field(default_factory=list)
    summary: str = Field(..., description="Human-readable summary of the orchestrator's decision")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
