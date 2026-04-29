"""
agents/analyst_team/models.py
⚠️  DEPRECATED — models have moved to `models/analyst.py`.
This shim preserves backward-compatibility during the transition.
"""
from models.analyst import AnalysisRequest, AnalysisResult, AnalysisReport, SignalType

__all__ = ["AnalysisRequest", "AnalysisResult", "AnalysisReport", "SignalType"]