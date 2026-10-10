"""
Branching engine module - determines next scenarios based on profile.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from config.settings import IntelligenceDimension, ConfidenceLevel
from scoring.deterministic_scorer import IntelligenceProfile, Scenario


@dataclass
class BranchDecision:
    """Result of a branching decision."""
    should_branch: bool
    target_section: Optional[str] = None
    target_tier: int = 1
    priority: float = 0.0
    reason: str = ""
    target_dimensions: List[IntelligenceDimension] = field(default_factory=list)


class BranchingEngine:
    """
    Determines branching paths based on intelligence profile scores
    and confidence levels. Prioritizes dimensions with high scores
    but low confidence (most signal, least certainty).
    """

    # Branching thresholds: dimension -> config
    BRANCH_TRIGGERS = {
        IntelligenceDimension.SPATIAL_TRANSFORMATIONAL: {
            "threshold": 18,
            "max_possible": 45,
            "section": "SECTION_A",
            "label": "Spatial Intelligence Deep Branch",
        },
        IntelligenceDimension.INTERPERSONAL: {
            "threshold": 10,
            "max_possible": 45,
            "section": "SECTION_B",
            "label": "Social Intelligence Deep Branch",
            "combined_with": IntelligenceDimension.INTRAPERSONAL,
            "combined_threshold": 20,
        },
        IntelligenceDimension.LOGICAL_MATHEMATICAL: {
            "threshold": 11,
            "max_possible": 50,
            "section": "SECTION_C",
            "label": "Logical-Mathematical Deep Branch",
            "combined_with": IntelligenceDimension.FLUID_INTELLIGENCE,
            "combined_threshold": 22,
        },
        IntelligenceDimension.EXISTENTIAL: {
            "threshold": 10,
            "max_possible": 20,
            "section": "SECTION_E",
            "label": "Existential Intelligence Deep Branch",
        },
    }

    def evaluate_branching(
        self, profile: IntelligenceProfile
    ) -> List[BranchDecision]:
        """Evaluate all possible branching decisions."""
        decisions = []

        for dimension, trigger_config in self.BRANCH_TRIGGERS.items():
            decision = self._evaluate_single_branch(
                profile, dimension, trigger_config
            )
            if decision.should_branch:
                decisions.append(decision)

        # Always check for learning ability longitudinal
        learning_decision = self._evaluate_learning_ability_branch(profile)
        if learning_decision.should_branch:
            decisions.append(learning_decision)

        return sorted(decisions, key=lambda d: d.priority, reverse=True)

    def _evaluate_single_branch(
        self,
        profile: IntelligenceProfile,
        dimension: IntelligenceDimension,
        config: Dict[str, Any],
    ) -> BranchDecision:
        """Evaluate a single branching possibility."""
        dim_score = profile.dimensions[dimension]
        threshold = config["threshold"]
        section = config["section"]
        label = config["label"]

        # Use percentile score if available, otherwise normalize
        if dim_score.percentile is not None:
            normalized_score = dim_score.percentile / 100.0
        elif dim_score.max_possible > 0:
            normalized_score = dim_score.raw_score / dim_score.max_possible
        else:
            normalized_score = 0.0

        # Check if score exceeds threshold
        if normalized_score < (threshold / 100.0):
            return BranchDecision(should_branch=False, reason="Score below threshold")

        # Calculate priority based on score and confidence
        priority = normalized_score * dim_score.confidence.value_num * 100

        # Check for combined dimensions
        if "combined_with" in config:
            combined_dim = config["combined_with"]
            combined_threshold = config["combined_threshold"]
            combined_score = profile.dimensions[combined_dim]

            if combined_score.percentile is not None:
                combined_normalized = combined_score.percentile / 100.0
            elif combined_score.max_possible > 0:
                combined_normalized = combined_score.raw_score / combined_score.max_possible
            else:
                combined_normalized = 0.0

            if combined_normalized < (combined_threshold / 100.0):
                return BranchDecision(should_branch=False, reason="Combined dimension below threshold")

        return BranchDecision(
            should_branch=True,
            target_section=section,
            target_tier=2,
            priority=priority,
            reason=f"{label} detected at {normalized_score:.2f}",
            target_dimensions=[dimension],
        )

    def _evaluate_learning_ability_branch(
        self, profile: IntelligenceProfile
    ) -> BranchDecision:
        """Check for learning ability longitudinal patterns."""
        trajectory = profile.learning_trajectory

        if trajectory.trajectory_type == "accelerating":
            return BranchDecision(
                should_branch=True,
                target_section="SECTION_F",
                target_tier=2,
                priority=0.85,
                reason="Accelerating learning trajectory detected",
                target_dimensions=[IntelligenceDimension.LEARNING_ABILITY],
            )
        elif trajectory.trajectory_type == "improving":
            return BranchDecision(
                should_branch=True,
                target_section="SECTION_F",
                target_tier=2,
                priority=0.70,
                reason="Improving learning trajectory detected",
                target_dimensions=[IntelligenceDimension.LEARNING_ABILITY],
            )

        return BranchDecision(should_branch=False, reason="No learning trajectory branch")

    def get_next_scenario(
        self,
        profile: IntelligenceProfile,
        current_tier: int,
    ) -> Tuple[str, int]:
        """Get the next scenario recommendation based on profile."""
        decisions = self.evaluate_branching(profile)

        if decisions:
            return decisions[0].target_section, decisions[0].target_tier

        return f"PART_{current_tier}", current_tier

    def should_branch_to_deep_assessment(
        self,
        profile: IntelligenceProfile,
        confidence_threshold: ConfidenceLevel = ConfidenceLevel.HIGH,
    ) -> bool:
        """Determine if user should do deep assessment branching."""
        for dimension, dim_score in profile.dimensions.items():
            if (dim_score.confidence == confidence_threshold or
                dim_score.confidence == ConfidenceLevel.VERY_HIGH):
                if dim_score.max_tier_reached < 3:
                    return True

        return False