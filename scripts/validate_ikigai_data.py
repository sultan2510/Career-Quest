"""Check that the published occupation snapshot has complete, plausible source fields."""
import json
import math
from pathlib import Path

root = Path(__file__).resolve().parents[1]
snapshot = json.loads((root / "frontend/lib/data/occupation-evidence.json").read_text(encoding="utf-8"))
expected = {"design", "data", "environment", "software", "education", "health", "product", "journalism"}
assert set(snapshot["occupations"]) == expected
assert set(snapshot["pk_earnings_major_groups_2025"]) == {str(n) for n in range(1, 10)}
for career, occupation in snapshot["occupations"].items():
    assert set(occupation["interests"]) == {"Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"}, career
    assert occupation["description"] and occupation["keywords"] and set(occupation["requirements"]) == {"logical", "spatial", "verbal", "inter", "intra", "bodily", "musical", "naturalistic", "existential", "fluid", "learning", "adapt", "creative"}, career
    assert all(math.isfinite(v) and 0 <= v <= 1 for v in occupation["requirements"].values()), career
    assert occupation["us"]["median_annual_usd"] > 0 and occupation["us"]["annual_openings"] > 0, career
    assert occupation["pk"]["employment_thousands_2021"] > 0 and occupation["pk"]["employment_thousands_2025"] > 0, career
    assert occupation["pk"]["median_hourly_pkr_2025_major_group"] == snapshot["pk_earnings_major_groups_2025"][occupation["pk"]["isco2_proxy"][0]], career
print(f"Validated {len(expected)} occupations and 9 Pakistan earnings groups")
