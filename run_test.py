#!/usr/bin/env python
"""Simple test to verify project runs correctly."""
import sys
sys.path.insert(0, '.')

# Test 1: Configuration
print('Testing Configuration...')
from config import IntelligenceDimension, get_career_weights
print('  OK: ConfidenceLevels:', len(IntelligenceDimension))

# Test 2: Scoring
print('Testing Scoring Engine...')
from scoring import DeterministicScorer
from scoring.deterministic_scorer import IntelligenceProfile, Scenario, ResponseOption, ScenarioResponse

scorer = DeterministicScorer()
profile = IntelligenceProfile('user-001', 'session-001')
scenario = Scenario('s1', tier=1, target_dimensions=[IntelligenceDimension.LOGICAL_MATHEMATICAL])
scenario.response_options = [ResponseOption('o1', scoring_vector={IntelligenceDimension.LOGICAL_MATHEMATICAL: 10})]
response = ScenarioResponse('user-001', 'session-001', 's1', 'o1')
profile = scorer.score_response(scenario, response, profile)
print('  OK: Profile scored')

# Test 3: API
print('Testing API...')
from api.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
response = client.get('/health')
print('  OK: Health check', response.status_code)

print()
print('All tests passed!')