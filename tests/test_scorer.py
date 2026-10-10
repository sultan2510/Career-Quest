"""Regressions for the original scoring engine used by the mentor adapter."""
import numpy as np
import pytest

from config.settings import IntelligenceDimension as D
from scoring import DeterministicScorer
from scoring.deterministic_scorer import IntelligenceProfile, ResponseOption, Scenario, ScenarioResponse
from scoring.profile_vector import ProfileVectorizer


def answer(scorer, profile, scenario, choice):
    return scorer.score_response(scenario, ScenarioResponse('u', 's', scenario.scenario_id, choice), profile)


def test_zero_choice_still_records_available_dimension_and_reduces_score():
    scorer = DeterministicScorer()
    profile = IntelligenceProfile('u', 's')
    scenario = Scenario('s1', target_dimensions=[D.LOGICAL_MATHEMATICAL])
    scenario.response_options = [ResponseOption('high', scoring_vector={D.LOGICAL_MATHEMATICAL: 10}), ResponseOption('zero')]
    answer(scorer, profile, scenario, 'high')
    answer(scorer, profile, scenario, 'zero')
    score = profile.dimensions[D.LOGICAL_MATHEMATICAL]
    assert score.raw_score == 10
    assert score.max_possible == 20
    assert score.score_history == [10, 0]
    assert score.scenarios_assessed == 2


def test_zero_only_scenario_does_not_crash_after_positive_history():
    scorer = DeterministicScorer()
    profile = IntelligenceProfile('u', 's')
    scenario = Scenario('s1', target_dimensions=[D.INTERPERSONAL])
    scenario.response_options = [ResponseOption('a', scoring_vector={D.INTERPERSONAL: 10})]
    for _ in range(3):
        answer(scorer, profile, scenario, 'a')
    scenario.response_options = [ResponseOption('b', scoring_vector={D.INTERPERSONAL: 0})]
    answer(scorer, profile, scenario, 'b')
    assert profile.total_scenarios_completed == 4


def test_percentile_uses_population_distribution_without_optional_scipy():
    profile = IntelligenceProfile('u', 's')
    score = profile.dimensions[D.LOGICAL_MATHEMATICAL]
    score.raw_score, score.max_possible = 8, 10
    DeterministicScorer().compute_percentiles(profile, {D.LOGICAL_MATHEMATICAL: {'mean': 0.5, 'std': 0.15}})
    assert score.percentile == pytest.approx(97.7, abs=0.1)


def test_career_weights_do_not_inflate_minimum_thresholds():
    profile = IntelligenceProfile('u', 's')
    profile.dimensions[D.LOGICAL_MATHEMATICAL].percentile = 60
    vectorizer = ProfileVectorizer([D.LOGICAL_MATHEMATICAL])
    vector = vectorizer.vectorize_profile(profile)
    passes, details = vectorizer.check_thresholds(vector, {D.LOGICAL_MATHEMATICAL: 70})
    assert not passes
    assert details[D.LOGICAL_MATHEMATICAL]['user_score'] == pytest.approx(0.6)


def test_euclidean_similarity_is_bounded_for_weighted_vectors():
    assert ProfileVectorizer().compute_similarity(np.array([3.0]), np.array([0.0]), 'euclidean') == 0
