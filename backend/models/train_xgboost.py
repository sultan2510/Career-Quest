#!/usr/bin/env python3
"""Train an XGBoost model to predict intelligence dimension scores from
scenario response patterns.

Training data is generated synthetically from the deterministic scorer's
known scoring vectors in catalog.json: for each scenario, every possible
option's scoring vector is treated as a training sample, with the response
option selected as a one-hot feature. The target is the per-dimension points
earned. This produces a model that learns the rubric mapping, enabling
real ML inference while staying consistent with the existing deterministic
results.

Usage:
    python -m models.train_xgboost
"""

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import IntelligenceDimension
from scoring.deterministic_scorer import DeterministicScorer, IntelligenceProfile, Scenario, ScenarioResponse, ResponseOption
from backend.rag_service import load_catalog  # noqa: E402

DIMENSIONS = list(IntelligenceDimension)
NUM_DIMENSIONS = len(DIMENSIONS)

# Dimension label mapping (matches config/settings.py)
DIM_LABELS = {
    IntelligenceDimension.LOGICAL_MATHEMATICAL: "logical-mathematical",
    IntelligenceDimension.SPATIAL_TRANSFORMATIONAL: "spatial-transformational",
    IntelligenceDimension.SPATIAL_ANALYTICAL: "spatial-analytical",
    IntelligenceDimension.SPATIAL_OBJECT_VISUAL: "spatial-object-visual",
    IntelligenceDimension.VERBAL_LINGUISTIC: "verbal-linguistic",
    IntelligenceDimension.INTERPERSONAL: "interpersonal",
    IntelligenceDimension.INTRAPERSONAL: "intrapersonal",
    IntelligenceDimension.BODILY_KINESTHETIC: "bodily-kinesthetic",
    IntelligenceDimension.MUSICAL: "musical",
    IntelligenceDimension.NATURALISTIC: "naturalistic",
    IntelligenceDimension.EXISTENTIAL: "existential",
    IntelligenceDimension.FLUID_INTELLIGENCE: "fluid-intelligence",
    IntelligenceDimension.LEARNING_ABILITY: "learning-ability",
    IntelligenceDimension.CAREER_ADAPTABILITY: "career-adaptability",
    IntelligenceDimension.CREATIVE_PROBLEM_SOLVING: "creative-problem-solving",
    IntelligenceDimension.EMOTIONAL_INTELLIGENCE: "emotional-intelligence",
    IntelligenceDimension.LEADERSHIP: "leadership",
    IntelligenceDimension.SYSTEMS_THINKING: "systems-thinking",
}


def generate_training_data(catalog_path: Path | None = None) -> tuple[np.ndarray, np.ndarray, list[str], dict]:
    """Build synthetic training samples from catalog scenario scoring vectors.

    Features: one-hot selected option + baseline profile stats
    Targets:  per-dimension scored points for the selected option
    """
    catalog = json.loads((catalog_path or (Path(__file__).resolve().parents[1] / "backend" / "catalog.json")).read_text(encoding="utf-8"))
    scenarios: list[Scenario] = []
    all_options: list[tuple[str, str]] = []

    for entry in catalog.get("dna_scenarios", []):
        scenario = Scenario(entry["id"], title=entry["title"], tier=2 if entry.get("parent") else 1)
        for option_id, score_vector in entry.get("scores", {}).items():
            scoring_vector = {IntelligenceDimension(k): v for k, v in score_vector.items() if k in {d.value for d in DIMENSIONS}}
            opt = ResponseOption(option_id, "", scoring_vector=scoring_vector)
            scenario.response_options.append(opt)
        scenarios.append(scenario)

    # Build feature rows: for each (scenario, option) pair, one-hot the option
    # with target = the scoring vector for that option
    feature_names: list[str] = []
    rows: list[list[float]] = []
    targets: list[list[float]] = []
    dimension_index: dict[str, int] = {}

    for i, dim in enumerate(DIMENSIONS):
        dimension_index[dim.value] = i
        feature_names.append(f"target_{DIM_LABELS[dim]}")

    option_id_map: dict[tuple[str, str], int] = {}
    for scenario in scenarios:
        for opt in scenario.response_options:
            key = (scenario.scenario_id, opt.option_id)
            if key not in option_id_map:
                option_id_map[key] = len(option_id_map)
                feature_names.append(f"opt_{key[0]}_{key[1]}")

    n_features = NUM_DIMENSIONS + len(option_id_map)

    for scenario in scenarios:
        for opt in scenario.response_options:
            features = [0.0] * n_features
            key = (scenario.scenario_id, opt.option_id)
            features[NUM_DIMENSIONS + option_id_map[key]] = 1.0

            target = [0.0] * NUM_DIMENSIONS
            for dim, points in opt.scoring_vector.items():
                idx = DIMENSIONS.index(dim)
                target[idx] = float(points)

            rows.append(features)
            targets.append(target)

    X = np.array(rows, dtype=np.float32)
    Y = np.array(targets, dtype=np.float32)
    return X, Y, feature_names, dimension_index


def train_model(X: np.ndarray, Y: np.ndarray, feature_names: list[str],
                dimension_index: dict) -> Any:
    """Train one XGBoost regressor per dimension."""
    import xgboost as xgb

    models: list[Any] = []
    for i in range(NUM_DIMENSIONS):
        # Multi-output regression: train per-dimension, then combine
        model = xgb.XGBRegressor(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.3,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="rmse",
        )
        model.fit(X, Y[:, i])
        models.append(model)

    return _BundledBooster(models, feature_names, dimension_index)


class _BundledBooster:
    """Wraps multiple per-dimension XGBoost models for unified prediction."""

    def __init__(self, models: list, feature_names: list[str], dimension_index: dict):
        self.models = models
        self.feature_names = feature_names
        self.dimension_index = dimension_index

    def predict(self, dmatrix) -> np.ndarray:
        """Return predictions array of shape (NUM_DIMENSIONS,)."""
        features = dmatrix if isinstance(dmatrix, np.ndarray) else dmatrix.data
        preds = [model.predict(features.reshape(1, -1))[0] for model in self.models]
        return np.array(preds)


def save_model(booster: _BundledBooster, output_path: Path) -> None:
    """Serialize the model bundle as JSON with base64-embedded boosters."""
    import base64
    import tempfile

    model_data = {
        "feature_names": booster.feature_names,
        "dimension_index": booster.dimension_index,
        "n_dimensions": NUM_DIMENSIONS,
        "dimension_labels": [DIM_LABELS[dim] for dim in DIMENSIONS],
        "models": [],
    }

    for i, model in enumerate(booster.models):
        booster_obj = model.get_booster()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name
        booster_obj.save_model(tmp_path)
        with open(tmp_path, "rb") as f:
            booster_bytes = f.read()
        Path(tmp_path).unlink(missing_ok=True)
        model_data["models"].append({
            "dimension": DIMENSIONS[i].value,
            "booster_b64": base64.b64encode(booster_bytes).decode("ascii"),
        })

    output_path.write_text(json.dumps(model_data, indent=2), encoding="utf-8")
    print(f"Saved XGBoost model to {output_path} ({output_path.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    print("Generating training data from catalog scoring vectors...")
    X, Y, feature_names, dimension_index = generate_training_data()
    print(f"Samples: {len(X)}, Features: {len(feature_names)}, Dimensions: {NUM_DIMENSIONS}")

    print("Training XGBoost models (one per dimension)...")
    booster = train_model(X, Y, feature_names, dimension_index)

    output = Path(__file__).resolve().parent / "dna_xgboost.json"
    save_model(booster, output)
    print("Done.")
