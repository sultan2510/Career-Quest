"""
Profile vectorization for user matching and retrieval.

Converts the human-readable intelligence profile into a mathematical
vector representation for similarity computation in the RAG retrieval layer.
"""

from typing import Dict, List, Optional, Any
import numpy as np

from config.settings import IntelligenceDimension, ConfidenceLevel, get_career_weights


# Canonical dimension ordering for vector construction
DIMENSION_ORDER = [
    IntelligenceDimension.SPATIAL_TRANSFORMATIONAL,
    IntelligenceDimension.SPATIAL_ANALYTICAL,
    IntelligenceDimension.SPATIAL_OBJECT_VISUAL,
    IntelligenceDimension.LOGICAL_MATHEMATICAL,
    IntelligenceDimension.VERBAL_LINGUISTIC,
    IntelligenceDimension.INTERPERSONAL,
    IntelligenceDimension.INTRAPERSONAL,
    IntelligenceDimension.BODILY_KINESTHETIC,
    IntelligenceDimension.MUSICAL,
    IntelligenceDimension.NATURALISTIC,
    IntelligenceDimension.EXISTENTIAL,
    IntelligenceDimension.FLUID_INTELLIGENCE,
    IntelligenceDimension.LEARNING_ABILITY,
    IntelligenceDimension.CAREER_ADAPTABILITY,
    IntelligenceDimension.CREATIVE_PROBLEM_SOLVING,
    IntelligenceDimension.EMOTIONAL_INTELLIGENCE,
    IntelligenceDimension.LEADERSHIP,
    IntelligenceDimension.SYSTEMS_THINKING,
]


# Mapping from ConfidenceLevel to numerical weight
CONFIDENCE_WEIGHTS = {
    ConfidenceLevel.VERY_LOW: 0.2,
    ConfidenceLevel.LOW: 0.4,
    ConfidenceLevel.MODERATE: 0.6,
    ConfidenceLevel.HIGH: 0.8,
    ConfidenceLevel.VERY_HIGH: 1.0,
}


class ProfileVectorizer:
    """
    Converts intelligence profiles into mathematical vectors for
    similarity computation. Uses percentile scores when available,
    falling back to normalized raw scores.
    """

    def __init__(self, dimension_order: Optional[List[IntelligenceDimension]] = None):
        self.dimension_order = dimension_order or DIMENSION_ORDER
        self.career_weights = get_career_weights().weights

    def vectorize_profile(self, profile: Any) -> np.ndarray:
        """Convert an intelligence profile into a vector.

        Args:
            profile: IntelligenceProfile instance

        Returns:
            numpy array of normalized scores
        """
        score_vector = []

        for dimension in self.dimension_order:
            dim_score = profile.dimensions[dimension]

            # Use percentile if available, otherwise normalize raw score
            if dim_score.percentile is not None:
                score = dim_score.percentile / 100.0
            elif dim_score.max_possible > 0:
                score = dim_score.raw_score / dim_score.max_possible
            else:
                score = 0.0

            # Apply career weight multiplier
            weight = self.career_weights.get(dimension, 1.0)
            weighted_score = score * weight

            score_vector.append(round(weighted_score, 4))

        return np.array(score_vector)

    def get_confidence_vector(self, profile: Any) -> np.ndarray:
        """Get confidence levels as a vector.

        Args:
            profile: IntelligenceProfile instance

        Returns:
            numpy array of confidence weights
        """
        confidence_vector = []

        for dimension in self.dimension_order:
            dim_score = profile.dimensions[dimension]
            confidence_vector.append(
                CONFIDENCE_WEIGHTS.get(dim_score.confidence, 0.2)
            )

        return np.array(confidence_vector)

    def compute_similarity(
        self,
        profile_vector: np.ndarray,
        career_vector: np.ndarray,
        method: str = "cosine",
    ) -> float:
        """
        Compute similarity between a user profile vector and a career
        requirement vector.

        Args:
            profile_vector: User's profile vector
            career_vector: Career requirement vector
            method: Similarity method (cosine, euclidean, hybrid)

        Returns:
            Similarity score between 0 and 1
        """
        if method == "cosine":
            return self._cosine_similarity(profile_vector, career_vector)
        elif method == "euclidean":
            return self._weighted_euclidean(profile_vector, career_vector)
        elif method == "hybrid":
            return self._hybrid_similarity(profile_vector, career_vector)
        else:
            raise ValueError(f"Unknown similarity method: {method}")

    def _cosine_similarity(
        self, vec_a: np.ndarray, vec_b: np.ndarray
    ) -> float:
        """Standard cosine similarity."""
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))

    def _weighted_euclidean(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray,
    ) -> float:
        """
        Weighted Euclidean distance converted to similarity score.
        """
        distance = np.linalg.norm(vec_a - vec_b)
        max_distance = np.sqrt(len(vec_a))  # max possible distance

        if max_distance == 0:
            return 0.0

        # Convert distance to similarity (0 to 1)
        return float(np.clip(1.0 - (distance / max_distance), 0.0, 1.0))

    def _hybrid_similarity(
        self,
        user_vec: np.ndarray,
        career_vec: np.ndarray,
        shape_weight: float = 0.4,
        magnitude_weight: float = 0.6,
    ) -> float:
        """
        Hybrid similarity metric fusing rank correlation (shape) with
        weighted Euclidean distance (magnitude).
        """
        try:
            from scipy.stats import spearmanr

            # Shape similarity via Spearman's rank correlation
            if len(set(user_vec)) > 1 and len(set(career_vec)) > 1:
                rank_corr, _ = spearmanr(user_vec, career_vec)
                shape_score = (rank_corr + 1) / 2  # Normalize from -1,1 to [0,1]
            else:
                shape_score = 0.5

            # Magnitude similarity via weighted Euclidean
            magnitude_score = self._weighted_euclidean(user_vec, career_vec)

            return float(shape_weight * shape_score + magnitude_weight * magnitude_score)
        except ImportError:
            # Fallback to cosine if scipy not available
            return self._cosine_similarity(user_vec, career_vec)

    def check_thresholds(
        self,
        profile_vector: np.ndarray,
        thresholds: Dict[IntelligenceDimension, float],
    ) -> tuple:
        """
        Check whether the user meets all minimum thresholds for a career.

        Args:
            profile_vector: User's profile vector
            thresholds: Minimum thresholds per dimension

        Returns:
            Tuple of (passes: bool, details: dict)
        """
        profile_dict = dict(zip(self.dimension_order, profile_vector))
        all_pass = True
        details = {}

        for dimension, min_percentile in thresholds.items():
            user_score = profile_dict.get(dimension, 0.0) / self.career_weights.get(dimension, 1.0)
            threshold_weighted = min_percentile / 100.0
            margin = user_score - threshold_weighted

            passes = margin >= 0
            if not passes:
                all_pass = False

            details[dimension] = {
                "user_score": user_score,
                "threshold": threshold_weighted,
                "margin": margin,
                "passes": passes,
            }

        return all_pass, details


# Legacy class alias for backward compatibility
class ProfileVector(ProfileVectorizer):
    """Legacy alias for ProfileVectorizer."""

    def __init__(self, dimensions: int = 384):
        super().__init__()
        self.dimensions = dimensions

    def vectorize(
        self,
        profile: Dict[str, Any],
        skills: Optional[List[str]] = None,
        interests: Optional[List[str]] = None,
        values: Optional[List[str]] = None
    ) -> np.ndarray:
        """Create a vector representation of a user profile (legacy method)."""
        # Create a simple profile object for compatibility
        class SimpleProfile:
            def __init__(self, p):
                self.dimensions = p.get("dimensions", {})

        simple_profile = SimpleProfile({"dimensions": profile})
        return self.vectorize_profile(simple_profile)
