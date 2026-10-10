"""Application settings and configuration."""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class IntelligenceDimension(str, Enum):
    """Intellectual dimensions for learning style profiling."""
    SPATIAL_TRANSFORMATIONAL = "spatial_transformational"
    SPATIAL_ANALYTICAL = "spatial_analytical"
    SPATIAL_OBJECT_VISUAL = "spatial_object_visual"
    LOGICAL_MATHEMATICAL = "logical_mathematical"
    VERBAL_LINGUISTIC = "verbal_linguistic"
    INTERPERSONAL = "interpersonal"
    INTRAPERSONAL = "intrapersonal"
    BODILY_KINESTHETIC = "bodily_kinesthetic"
    MUSICAL = "musical"
    NATURALISTIC = "naturalistic"
    EXISTENTIAL = "existential"
    FLUID_INTELLIGENCE = "fluid_intelligence"
    LEARNING_ABILITY = "learning_ability"
    CAREER_ADAPTABILITY = "career_adaptability"
    CREATIVE_PROBLEM_SOLVING = "creative_problem_solving"
    EMOTIONAL_INTELLIGENCE = "emotional_intelligence"
    LEADERSHIP = "leadership"
    SYSTEMS_THINKING = "systems_thinking"


class RIASECDimension(str, Enum):
    """RIASEC vocational preference dimensions."""
    REALISTIC = "realistic"
    INVESTIGATIVE = "investigative"
    ARTISTIC = "artistic"
    SOCIAL = "social"
    ENTERPRISING = "enterprising"
    CONVENTIONAL = "conventional"


class SatisfactionDimension(str, Enum):
    """Dimensions of career satisfaction."""
    OVERALL_SATISFACTION = "overall_satisfaction"
    MEANING_AND_PURPOSE = "meaning_and_purpose"
    FINANCIAL_SATISFACTION = "financial_satisfaction"
    WORK_LIFE_BALANCE = "work_life_balance"
    GROWTH_OPPORTUNITY = "growth_opportunity"
    SOCIAL_FULFILLMENT = "social_fulfillment"
    AUTONOMY = "autonomy"
    SKILL_UTILIZATION = "skill_utilization"
    ALIGNMENT_WITH_VALUES = "alignment_with_values"
    STRESS_LEVEL = "stress_level"


class ConfidenceLevel(str, Enum):
    """Confidence levels for assessment results."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"

    @property
    def value_num(self) -> float:
        """Convert to numeric value."""
        mapping = {
            "very_low": 0.2,
            "low": 0.4,
            "moderate": 0.6,
            "high": 0.8,
            "very_high": 1.0,
        }
        return mapping.get(self.value, 0.2)


class DecisionType(str, Enum):
    """Types of decisions in scenarios."""
    INDIVIDUAL = "individual"
    TEAM = "team"
    LEADERSHIP = "leadership"
    STEALTH = "stealth"


class ScenarioTheme(str, Enum):
    """Themes for career scenarios."""
    ETHICS = "ethics"
    COMPETITION = "competition"
    INNOVATION = "innovation"
    CAREER_DEVELOPMENT = "career_development"
    PERSONAL_GROWTH = "personal_growth"


class UserStatus(str, Enum):
    """User status indicators."""
    NEW = "new"
    ACTIVE = "active"
    LAPSED = "lapsed"


class SkillLevel(str, Enum):
    """Skill proficiency levels."""
    NOVICE = "novice"
    APPRENTICE = "apprentice"
    PRACTITIONER = "practitioner"
    EXPERT = "expert"
    MASTER = "master"


class CareerField(str, Enum):
    """Career field categories."""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    EDUCATION = "education"
    ENVIRONMENT = "environment"
    ARTS = "arts"
    GOVERNMENT = "government"
    NONPROFIT = "nonprofit"
    ACADEMIC = "academic"
    ENTREPRENEURSHIP = "entrepreneurship"


@dataclass
class CareerWeightMultiplier:
    """Weight multipliers for intelligence dimensions in career matching."""
    weights: Dict[IntelligenceDimension, float] = field(default_factory=lambda: {
        IntelligenceDimension.LOGICAL_MATHEMATICAL: 1.2,
        IntelligenceDimension.SPATIAL_TRANSFORMATIONAL: 1.1,
        IntelligenceDimension.SPATIAL_ANALYTICAL: 1.1,
        IntelligenceDimension.SPATIAL_OBJECT_VISUAL: 1.0,
        IntelligenceDimension.VERBAL_LINGUISTIC: 1.0,
        IntelligenceDimension.INTERPERSONAL: 1.15,
        IntelligenceDimension.INTRAPERSONAL: 1.1,
        IntelligenceDimension.BODILY_KINESTHETIC: 0.9,
        IntelligenceDimension.MUSICAL: 0.8,
        IntelligenceDimension.NATURALISTIC: 0.9,
        IntelligenceDimension.EXISTENTIAL: 0.85,
        IntelligenceDimension.FLUID_INTELLIGENCE: 1.3,
        IntelligenceDimension.LEARNING_ABILITY: 1.2,
        IntelligenceDimension.CAREER_ADAPTABILITY: 1.1,
        IntelligenceDimension.CREATIVE_PROBLEM_SOLVING: 1.05,
        IntelligenceDimension.EMOTIONAL_INTELLIGENCE: 1.1,
        IntelligenceDimension.LEADERSHIP: 1.05,
        IntelligenceDimension.SYSTEMS_THINKING: 1.15,
    })


@dataclass
class RIASECMapping:
    """Mapping from intelligence dimensions to RIASEC dimensions."""
    mappings: Dict[RIASECDimension, Dict[IntelligenceDimension, float]] = field(
        default_factory=lambda: {
            RIASECDimension.REALISTIC: {
                IntelligenceDimension.SPATIAL_TRANSFORMATIONAL: 0.35,
                IntelligenceDimension.SPATIAL_ANALYTICAL: 0.15,
                IntelligenceDimension.BODILY_KINESTHETIC: 0.3,
                IntelligenceDimension.NATURALISTIC: 0.2,
            },
            RIASECDimension.INVESTIGATIVE: {
                IntelligenceDimension.LOGICAL_MATHEMATICAL: 0.3,
                IntelligenceDimension.FLUID_INTELLIGENCE: 0.3,
                IntelligenceDimension.LEARNING_ABILITY: 0.15,
                IntelligenceDimension.SYSTEMS_THINKING: 0.15,
                IntelligenceDimension.CREATIVE_PROBLEM_SOLVING: 0.1,
            },
            RIASECDimension.ARTISTIC: {
                IntelligenceDimension.CREATIVE_PROBLEM_SOLVING: 0.3,
                IntelligenceDimension.MUSICAL: 0.15,
                IntelligenceDimension.SPATIAL_OBJECT_VISUAL: 0.25,
                IntelligenceDimension.EXISTENTIAL: 0.15,
                IntelligenceDimension.INTRAPERSONAL: 0.15,
            },
            RIASECDimension.SOCIAL: {
                IntelligenceDimension.INTERPERSONAL: 0.4,
                IntelligenceDimension.INTRAPERSONAL: 0.2,
                IntelligenceDimension.VERBAL_LINGUISTIC: 0.15,
                IntelligenceDimension.EMOTIONAL_INTELLIGENCE: 0.25,
            },
            RIASECDimension.ENTERPRISING: {
                IntelligenceDimension.LEADERSHIP: 0.35,
                IntelligenceDimension.INTERPERSONAL: 0.25,
                IntelligenceDimension.LOGICAL_MATHEMATICAL: 0.2,
                IntelligenceDimension.CAREER_ADAPTABILITY: 0.2,
            },
            RIASECDimension.CONVENTIONAL: {
                IntelligenceDimension.LOGICAL_MATHEMATICAL: 0.35,
                IntelligenceDimension.VERBAL_LINGUISTIC: 0.3,
                IntelligenceDimension.SPATIAL_ANALYTICAL: 0.15,
                IntelligenceDimension.CAREER_ADAPTABILITY: 0.2,
            },
        }
    )


@dataclass
class SatisfactionPredictorWeights:
    """Weights for predicting satisfaction from intelligence profile alignment."""
    dimension_satisfaction_correlations: Dict[SatisfactionDimension, Dict[str, float]] = field(
        default_factory=lambda: {
            SatisfactionDimension.SKILL_UTILIZATION: {
                "profile_career_cosine_similarity": 0.40,
                "top_strength_utilized": 0.35,
                "threshold_margin_average": 0.25,
            },
            SatisfactionDimension.MEANING_AND_PURPOSE: {
                "existential_score": 0.30,
                "intrapersonal_score": 0.30,
                "values_alignment_score": 0.40,
            },
            SatisfactionDimension.GROWTH_OPPORTUNITY: {
                "learning_ability_score": 0.40,
                "career_adaptability_score": 0.30,
                "career_growth_projection": 0.30,
            },
            SatisfactionDimension.SOCIAL_FULFILLMENT: {
                "interpersonal_score": 0.35,
                "career_social_demand": 0.35,
                "emotional_intelligence_score": 0.30,
            },
            SatisfactionDimension.AUTONOMY: {
                "intrapersonal_score": 0.35,
                "career_autonomy_level": 0.40,
                "leadership_score": 0.25,
            },
            SatisfactionDimension.FINANCIAL_SATISFACTION: {
                "career_median_salary_percentile": 0.50,
                "career_salary_growth_rate": 0.30,
                "career_demand_score": 0.20,
            },
            SatisfactionDimension.WORK_LIFE_BALANCE: {
                "career_average_hours": -0.40,
                "career_flexibility_score": 0.35,
                "intrapersonal_score": 0.25,
            },
            SatisfactionDimension.STRESS_LEVEL: {
                "career_stress_rating": -0.40,
                "emotional_intelligence_score": 0.30,
                "career_adaptability_score": 0.30,
            },
        }
    )


# Global configuration instances
_career_weights = CareerWeightMultiplier()
_riasec_mapping = RIASECMapping()
_satisfaction_weights = SatisfactionPredictorWeights()
config = CareerWeightMultiplier()  # type: ignore


def get_career_weights() -> CareerWeightMultiplier:
    return _career_weights


def get_riasec_mapping() -> RIASECMapping:
    return _riasec_mapping


def get_satisfaction_weights() -> SatisfactionPredictorWeights:
    return _satisfaction_weights