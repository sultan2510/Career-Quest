"""
Deterministic scoring engine for processing user responses and updating
intelligence profiles. Every scoring operation is reproducible and
auditable—the same response always produces the same score.
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import statistics
import uuid

from config.settings import (
    IntelligenceDimension,
    ConfidenceLevel,
    config,
)


class DimensionScore:
    """Score for a single intelligence dimension."""
    def __init__(self):
        self.raw_score: float = 0.0
        self.max_possible: float = 0.0
        self.percentile: Optional[float] = None
        self.confidence: ConfidenceLevel = ConfidenceLevel.VERY_LOW
        self.scenarios_assessed: int = 0
        self.max_tier_reached: int = 0
        self.score_history: List[float] = []
        self.last_updated: datetime = datetime.now(timezone.utc)


class LearningTrajectory:
    """Tracks learning ability through performance improvement over time."""
    def __init__(self):
        self.trial_scores: List[float] = []
        self.trial_timestamps: List[datetime] = []
        self.trajectory_type: Optional[str] = None
        self.growth_rate: float = 0.0
        self.consistency: float = 0.0


class IntelligenceProfile:
    """Complete multi-dimensional intelligence profile for a user."""
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.dimensions: Dict[IntelligenceDimension, DimensionScore] = {
            dim: DimensionScore() for dim in IntelligenceDimension
        }
        self.learning_trajectory = LearningTrajectory()
        self.riasec_scores: Dict[str, float] = {
            "realistic": 0.0, "investigative": 0.0, "artistic": 0.0,
            "social": 0.0, "enterprising": 0.0, "conventional": 0.0
        }
        self.riasec_code: Optional[str] = None
        self.total_scenarios_completed: int = 0
        self.total_branches_explored: int = 0
        self.flagged_inconsistencies: List[Dict[str, Any]] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)


class Scenario:
    """A career scenario."""
    def __init__(
        self,
        scenario_id: str,
        title: str = "",
        tier: int = 1,
        theme: str = "",
        target_dimensions: Optional[List[IntelligenceDimension]] = None,
    ):
        self.scenario_id = scenario_id
        self.title = title
        self.tier = tier
        self.theme = theme
        self.target_dimensions = target_dimensions or []
        self.response_options: List["ResponseOption"] = []
        self.description = ""
        self.difficulty = 5


class ResponseOption:
    """A response option within a scenario."""
    def __init__(self, option_id: str, text: str = "", scoring_vector: Optional[Dict[IntelligenceDimension, int]] = None):
        self.option_id = option_id
        self.text = text
        self.description = ""
        self.consequences: List[str] = []
        self.scoring_vector = scoring_vector or {}


class ScenarioResponse:
    """A user's response to a scenario."""
    def __init__(
        self,
        user_id: str,
        session_id: str,
        scenario_id: str,
        selected_option_id: str,
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.scenario_id = scenario_id
        self.selected_option_id = selected_option_id
        self.response_latency_ms: Optional[int] = None
        self.option_changes: int = 0
        self.timestamp = datetime.now(timezone.utc)


class ProfileVector:
    """Vector representation of intelligence profile."""
    def __init__(self):
        self.user_id = ""
        self.vector: List[float] = []
        self.dimension_order: List[IntelligenceDimension] = list(IntelligenceDimension)
        self.confidence_vector: List[float] = []
        self.timestamp = datetime.now(timezone.utc)


class DeterministicScorer:
    """
    Deterministic scoring engine that processes user responses and updates
    intelligence profiles. Every scoring operation is reproducible and
    auditable—the same response always produces the same score.
    """

    def __init__(self):
        from config.settings import get_riasec_mapping, get_career_weights
        self.riasec_mapping = get_riasec_mapping().mappings
        self.career_weights = get_career_weights().weights

    def score_response(
        self,
        scenario: Scenario,
        response: ScenarioResponse,
        current_profile: IntelligenceProfile,
    ) -> IntelligenceProfile:
        """Process a user response and return an updated intelligence profile."""
        # Step 1: Find the selected option and its scoring vector
        selected_option = self._find_selected_option(
            scenario, response.selected_option_id
        )
        if selected_option is None:
            raise ValueError(
                f"Option {response.selected_option_id} not found in "
                f"scenario {scenario.scenario_id}"
            )

        scoring_vector = selected_option.scoring_vector

        # Step 2: Apply scoring vector to profile
        updated_profile = self._apply_scoring_vector(
            current_profile, scoring_vector, scenario
        )

        # Step 3: Update confidence levels
        updated_profile = self._update_confidence(updated_profile, scenario)

        # Step 4: Update learning trajectory if applicable
        if IntelligenceDimension.LEARNING_ABILITY in scenario.target_dimensions:
            updated_profile = self._update_learning_trajectory(
                updated_profile, scoring_vector, response
            )

        # Step 5: Check for inconsistencies
        updated_profile = self._check_inconsistencies(
            updated_profile, scoring_vector, scenario
        )

        # Step 6: Recalculate RIASEC scores
        updated_profile = self._calculate_riasec(updated_profile)

        # Step 7: Update metadata
        updated_profile.total_scenarios_completed += 1
        updated_profile.updated_at = datetime.now(timezone.utc)

        return updated_profile

    def _find_selected_option(
        self, scenario: Scenario, option_id: str
    ) -> Optional[ResponseOption]:
        """Find the selected response option in the scenario."""
        for option in scenario.response_options:
            if option.option_id == option_id:
                return option
        return None

    def _apply_scoring_vector(
        self,
        profile: IntelligenceProfile,
        scoring_vector: Dict[IntelligenceDimension, int],
        scenario: Scenario,
    ) -> IntelligenceProfile:
        """Apply the scoring vector from a response to the intelligence profile."""
        assessed = set(scenario.target_dimensions)
        assessed.update(d for option in scenario.response_options for d in option.scoring_vector)
        for dimension in assessed:
            points = scoring_vector.get(dimension, 0)
            dim_score = profile.dimensions[dimension]

            # Update raw score
            dim_score.raw_score += float(points)

            # Update maximum possible score for this dimension
            max_for_this_scenario = max(
                opt.scoring_vector.get(dimension, 0)
                for opt in scenario.response_options
            ) if scenario.response_options else 0
            dim_score.max_possible += float(max_for_this_scenario)

            # Track score history for trajectory analysis
            dim_score.score_history.append(float(points))

            # Update scenarios assessed count
            if points > 0 or max_for_this_scenario > 0:
                dim_score.scenarios_assessed += 1

            # Update max tier reached
            if scenario.tier > dim_score.max_tier_reached:
                dim_score.max_tier_reached = scenario.tier

            dim_score.last_updated = datetime.now(timezone.utc)
            profile.dimensions[dimension] = dim_score

        return profile

    def _update_confidence(
        self, profile: IntelligenceProfile, scenario: Scenario
    ) -> IntelligenceProfile:
        """Update confidence levels based on assessment depth."""
        assessed = set(scenario.target_dimensions)
        assessed.update(d for option in scenario.response_options for d in option.scoring_vector)
        for dimension in assessed:
            dim_score = profile.dimensions[dimension]
            tier = dim_score.max_tier_reached
            scenarios = dim_score.scenarios_assessed

            if tier >= 4 and scenarios >= 4:
                dim_score.confidence = ConfidenceLevel.VERY_HIGH
            elif tier >= 3 and scenarios >= 3:
                dim_score.confidence = ConfidenceLevel.HIGH
            elif tier >= 2 and scenarios >= 2:
                dim_score.confidence = ConfidenceLevel.MODERATE
            elif scenarios >= 1:
                dim_score.confidence = ConfidenceLevel.LOW
            else:
                dim_score.confidence = ConfidenceLevel.VERY_LOW

            profile.dimensions[dimension] = dim_score

        return profile

    def _update_learning_trajectory(
        self,
        profile: IntelligenceProfile,
        scoring_vector: Dict[IntelligenceDimension, int],
        response: ScenarioResponse,
    ) -> IntelligenceProfile:
        """Track learning ability through performance improvement over time."""
        learning_score = scoring_vector.get(
            IntelligenceDimension.LEARNING_ABILITY, 0
        )
        trajectory = profile.learning_trajectory

        trajectory.trial_scores.append(float(learning_score))
        trajectory.trial_timestamps.append(response.timestamp)

        if len(trajectory.trial_scores) >= 2:
            scores = trajectory.trial_scores
            differences = [
                scores[i + 1] - scores[i] for i in range(len(scores) - 1)
            ]
            trajectory.growth_rate = statistics.mean(differences) if differences else 0.0

            # Determine trajectory type
            if all(d > 0 for d in differences):
                trajectory.trajectory_type = "accelerating"
            elif all(d >= 0 for d in differences) and any(d == 0 for d in differences):
                trajectory.trajectory_type = "plateau"
            elif trajectory.growth_rate > 0:
                trajectory.trajectory_type = "improving"
            elif trajectory.growth_rate < 0:
                trajectory.trajectory_type = "declining"
            else:
                trajectory.trajectory_type = "stable"

            # Calculate consistency
            if len(scores) >= 3:
                try:
                    abs_mean = statistics.mean(abs(d) for d in differences) if differences else 0.001
                    trajectory.consistency = 1.0 - (statistics.stdev(differences) / max(abs_mean, 0.001))
                except statistics.StatisticsError:
                    trajectory.consistency = 1.0

        profile.learning_trajectory = trajectory
        return profile

    def _check_inconsistencies(
        self,
        profile: IntelligenceProfile,
        scoring_vector: Dict[IntelligenceDimension, int],
        scenario: Scenario,
    ) -> IntelligenceProfile:
        """Flag inconsistencies in the profile."""
        assessed = set(scenario.target_dimensions)
        assessed.update(d for option in scenario.response_options for d in option.scoring_vector)
        for dimension in assessed:
            points = scoring_vector.get(dimension, 0)
            dim_score = profile.dimensions[dimension]

            if dim_score.scenarios_assessed >= 3 and len(dim_score.score_history) >= 3:
                recent_scores = dim_score.score_history[-3:]
                mean_score = statistics.mean(recent_scores)

                if dim_score.max_possible > 0:
                    scenario_max = max(
                        (opt.scoring_vector.get(dimension, 0) for opt in scenario.response_options),
                        default=0,
                    )
                    normalized_current = points / max(scenario_max, 1)
                    normalized_mean = mean_score / max(dim_score.max_possible / dim_score.scenarios_assessed, 1)

                    deviation = abs(normalized_current - normalized_mean)

                    if deviation > 0.5:
                        profile.flagged_inconsistencies.append({
                            "dimension": dimension.value,
                            "scenario_id": scenario.scenario_id,
                            "current_score": points,
                            "historical_mean": mean_score,
                            "deviation": deviation,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

        return profile

    def _calculate_riasec(
        self, profile: IntelligenceProfile
    ) -> IntelligenceProfile:
        """Translate intelligence profile into RIASEC dimensions."""
        for riasec_dim, intelligence_weights in self.riasec_mapping.items():
            score = 0.0
            total_weight = 0.0

            for intel_dim, weight in intelligence_weights.items():
                dim_score = profile.dimensions[intel_dim]
                if dim_score.max_possible > 0:
                    normalized = dim_score.raw_score / dim_score.max_possible
                    score += normalized * weight
                    total_weight += weight

            if total_weight > 0:
                profile.riasec_scores[riasec_dim.value] = score / total_weight

        # Generate three-letter RIASEC code
        sorted_riasec = sorted(
            profile.riasec_scores.items(), key=lambda x: x[1], reverse=True
        )
        profile.riasec_code = "".join(dim[0].upper() for dim, _ in sorted_riasec[:3])

        return profile

    def compute_percentiles(
        self,
        profile: IntelligenceProfile,
        population_stats: Dict[IntelligenceDimension, Dict[str, float]],
    ) -> IntelligenceProfile:
        """Compute percentile ranks for each dimension."""
        from statistics import NormalDist

        for dimension, dim_score in profile.dimensions.items():
            if dim_score.max_possible > 0 and dimension in population_stats:
                normalized_score = dim_score.raw_score / dim_score.max_possible
                pop_mean = population_stats[dimension].get("mean", 0.5)
                pop_std = population_stats[dimension].get("std", 0.15)

                if pop_std > 0:
                    z_score = (normalized_score - pop_mean) / pop_std
                    percentile = NormalDist().cdf(z_score) * 100
                    dim_score.percentile = round(percentile, 1)

                profile.dimensions[dimension] = dim_score

        return profile

    def generate_profile_vector(self, profile: IntelligenceProfile) -> ProfileVector:
        """Generate a vector representation of the profile."""
        from scoring.profile_vector import ProfileVectorizer
        vectorizer = ProfileVectorizer()
        return vectorizer.vectorize_profile(profile)
