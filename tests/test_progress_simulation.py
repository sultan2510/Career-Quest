import pytest
from pydantic import ValidationError

from backend.progress import ProgressSnapshot


def test_simulation_draft_is_accepted_with_existing_ikigai_answers():
    payload = {
        "v": 1,
        "country": "PK",
        "interests": {"R1": 4},
        "statedInterests": "Public service",
        "skillsAndProjects": "Built a school website",
        "mentorMessages": [
            {"id": "q1", "at": "2026-10-10T10:02:00Z", "role": "you", "text": "Which career?"},
            {"id": "a1", "at": "2026-10-10T10:03:00Z", "role": "yuki", "text": "Try design.",
             "sources": [{"n": 1, "title": "O*NET", "excerpt": "Design work"}]},
        ],
        "simulationDrafts": {
            "design": {
                "run_id": "run-1",
                "career_id": "design",
                "current_scene_id": "design:0",
                "started_at": "2026-10-10T10:00:00Z",
                "decision_log": [{
                    "scene_id": "design:0",
                    "user_choice": "Talk to students",
                    "timestamp": "2026-10-10T10:01:00Z",
                    "outcome": "The problem becomes clearer.",
                    "quality": 2,
                    "source": "choice",
                }],
            },
        },
    }
    validated = ProgressSnapshot.validate_payload(payload)
    assert validated.country == "PK"
    assert validated.interests["R1"] == 4
    assert validated.simulationDrafts["design"].decision_log[0].user_choice == "Talk to students"
    assert validated.mentorMessages[1].sources[0].title == "O*NET"


def test_simulation_draft_rejects_invalid_rating_and_mismatched_career():
    payload = {
        "simulationDrafts": {
            "design": {
                "run_id": "run-1", "career_id": "data", "current_scene_id": "data:0",
                "started_at": "now", "decision_log": [{
                    "scene_id": "data:0", "user_choice": "Choose", "timestamp": "now",
                    "enjoyment_rating": 6, "outcome": "Outcome", "source": "choice",
                }],
            },
        },
    }
    with pytest.raises(ValidationError):
        ProgressSnapshot.validate_payload(payload)
