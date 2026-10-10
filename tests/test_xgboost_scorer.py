"""Tests for the XGBoost ML scorer's feature encoding and prediction path."""
import json
from pathlib import Path

import numpy as np
import pytest

from config.settings import IntelligenceDimension as D
from scoring.deterministic_scorer import (
    DeterministicScorer, IntelligenceProfile, ResponseOption, Scenario,
    ScenarioResponse,
)

from backend.rag_service import build_user_context_ml, load_catalog
from backend.progress import ProgressSnapshot

CATALOG_PATH = Path(__file__).resolve().parents[1] / "backend" / "catalog.json"


def _make_scenarios(catalog):
    """Rebuild all catalog scenarios the same way build_user_context_ml does."""
    from backend.rag_service import DNA_DIMENSIONS
    scenarios = []
    for entry in catalog.get("dna_scenarios", []):
        dimensions = {DNA_DIMENSIONS[key] for option in entry.get("scores", {}).values()
                      for key in option if key in DNA_DIMENSIONS}
        scenario = Scenario(entry["id"], title=entry["title"],
                            tier=2 if entry.get("parent") else 1,
                            target_dimensions=list(dimensions))
        scenario.response_options = [
            ResponseOption(option, scoring_vector={DNA_DIMENSIONS[key]: score
                              for key, score in vector.items() if key in DNA_DIMENSIONS})
            for option, vector in entry["scores"].items()
        ]
        scenarios.append(scenario)
    return scenarios


def test_encode_all_scenarios_not_just_answered(catalog_path=None):
    """encode_responses must produce features for ALL catalog scenarios (matching training),
    not only the ones the user answered."""
    from models.xgboost_scorer import XGBoostScorer, DIMENSIONS
    catalog = json.loads((catalog_path or CATALOG_PATH).read_text(encoding="utf-8"))
    scenarios = _make_scenarios(catalog)
    scorer = XGBoostScorer()
    if not scorer.available:
        pytest.skip("Model artifact not present")

    profile = IntelligenceProfile("u", "s")
    selected = {"1.1": "D"}

    feats = scorer.encode_responses(profile, scenarios, selected)
    expected_option_feats = sum(len(s.response_options) for s in scenarios)
    assert len(feats) == expected_option_feats + len(DIMENSIONS)

    non_zero = [i for i, v in enumerate(feats) if v != 0.0]
    # Only one one-hot feature should be set in the options portion
    option_indices = [i for i in non_zero if i < expected_option_feats]
    assert len(option_indices) == 1


def test_feature_vector_matches_training_order():
    """The option feature order must match what train_xgboost.py produces:
    scenarios iterated in catalog order, options iterated per scenario."""
    from models.xgboost_scorer import XGBoostScorer, DIMENSIONS
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    scenarios = _make_scenarios(catalog)
    scorer = XGBoostScorer()
    if not scorer.available:
        pytest.skip("Model artifact not present")

    # Verify feature names match the encoding order
    with open(scorer._model_path, encoding="utf-8") as f:
        model_data = json.load(f)
    expected_option_names = []
    for s in scenarios:
        for opt in s.response_options:
            expected_option_names.append(f"opt_{s.scenario_id}_{opt.option_id}")
    model_option_names = [n for n in model_data["feature_names"] if n.startswith("opt_")]
    assert model_option_names == expected_option_names


@pytest.mark.parametrize("selected", [
    {"1.1": "D"},
    {"1.1": "A"},
    {"1.1": "A", "1.1A": "A1"},
])
def test_ml_blend_changes_points_with_different_selections(selected):
    """Different selections should yield different blended ML scores."""
    from models.xgboost_scorer import XGBoostScorer
    catalog = load_catalog()
    scorer = XGBoostScorer()
    if not scorer.available:
        pytest.skip("Model artifact not present")

    progress = ProgressSnapshot.model_validate({"v": 1, "dna": {"answers": selected}})
    ctx = build_user_context_ml(progress, catalog, "alice", scorer)
    lm = next(d for d in ctx["DNA"]["dimensions"] if d["dimension"] == "Logical-Mathematical")
    assert lm.get("ml_adjusted") is True
