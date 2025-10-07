"""
Type definitions for the Code Review Agent.
"""

from typing import Dict, List, Optional, TypedDict


class AnalysisResult(TypedDict):
    """Result of a single analysis."""
    issues: List[Dict[str, str]]
    summary: str
    passed: bool


class CodeReviewState(TypedDict):
    """State object that flows through the review graph."""
    # Input
    code: str
    file_extension: str
    language: str
    
    # Analysis Results
    analysis_results: Dict[str, AnalysisResult]
    
    # Output
    feedback: str
    error: Optional[str]
    
    # Metadata
    metadata: Dict[str, any]
