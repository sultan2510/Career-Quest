"""Scoring module for career decision assessment."""

from .deterministic_scorer import (
    DeterministicScorer,
    IntelligenceProfile,
    DimensionScore,
    LearningTrajectory,
    Scenario,
    ResponseOption,
    ScenarioResponse,
    ProfileVector as ProfileVectorCore,
)
from .profile_vector import ProfileVectorizer
from .branching_engine import BranchingEngine, BranchDecision

# For backward compatibility
ProfileVector = ProfileVectorizer

__all__ = [
    "DeterministicScorer",
    "IntelligenceProfile",
    "DimensionScore",
    "LearningTrajectory",
    "Scenario",
    "ResponseOption",
    "ScenarioResponse",
    "ProfileVector",
    "ProfileVectorizer",
    "BranchingEngine",
    "BranchDecision",
]