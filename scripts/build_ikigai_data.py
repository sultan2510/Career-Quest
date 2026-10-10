"""Build the checked-in occupation snapshot from official O*NET and ILOSTAT CSV files.

Run from the repository root: python scripts/build_ikigai_data.py
The BLS snapshot is transcribed from the linked 2025 OEWS/2025-35 EP tables.
This script refuses missing O*NET occupations and missing RIASEC axes.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONET = ROOT / "data" / "onet-31"
OUT = ROOT / "frontend" / "lib" / "data" / "occupation-evidence.json"

SOC = {
    "design": "15-1255.00", "data": "15-2051.00", "environment": "19-2041.00",
    "software": "15-1252.00", "education": "25-2031.00", "health": "29-1141.00",
    "product": "13-1082.00", "journalism": "27-3023.00",
}

# This crosswalk is an explicit modelling hypothesis, not an O*NET recommendation.
# O*NET 31.0 renamed Cross-Functional Skills to Transferable Skills and changed
# Work Styles from IM (1..5) to WI (-3..3). Keep their scales separate below.
CROSSWALK = {
    "logical": [("abilities", "Mathematical Reasoning"), ("abilities", "Number Facility"), ("essential_skills", "Mathematics")],
    "spatial": [("abilities", "Visualization"), ("abilities", "Spatial Orientation")],
    "verbal": [("abilities", "Oral Expression"), ("abilities", "Written Expression"), ("abilities", "Written Comprehension")],
    "inter": [("transferable_skills", "Social Perceptiveness"), ("transferable_skills", "Service Orientation"), ("transferable_skills", "Coordination")],
    "intra": [("work_styles", "Self-Control"), ("work_styles", "Initiative")],
    "bodily": [("abilities", "Manual Dexterity"), ("abilities", "Finger Dexterity"), ("abilities", "Control Precision")],
    "musical": [("knowledge", "Fine Arts"), ("abilities", "Hearing Sensitivity")],
    "naturalistic": [("knowledge", "Biology"), ("knowledge", "Geography")],
    "existential": [("knowledge", "Philosophy and Theology")],
    "fluid": [("abilities", "Inductive Reasoning"), ("abilities", "Deductive Reasoning"), ("abilities", "Category Flexibility")],
    "learning": [("essential_skills", "Active Learning"), ("essential_skills", "Learning Strategies")],
    "adapt": [("work_styles", "Adaptability"), ("work_styles", "Tolerance for Ambiguity"), ("work_styles", "Perseverance")],
    "creative": [("abilities", "Originality"), ("abilities", "Fluency of Ideas")],
}

# Hand-mapped proxies at ILOSTAT's available resolution. These are not SOC-to-ISCO
# equivalences. Several distinct careers necessarily share an ISCO-08 group.
ISCO2 = {
    "design": "25", "data": "25", "environment": "21", "software": "25",
    "education": "23", "health": "22", "product": "24", "journalism": "26",
}


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def onet_value(table, soc, element, scale):
    vals = [float(r["Data Value"]) for r in table
            if r["O*NET-SOC Code"] == soc and r["Element Name"] == element
            and r["Scale ID"] == scale and r["Data Value"]]
    return sum(vals) / len(vals) if vals else None


def ilo_series(path, code, prefix, currency=None):
    out = {}
    for r in rows(path):
        if r["ref_area"] != "PAK" or r["sex"] != "SEX_T" or r["classif1"] != prefix + code:
            continue
        if currency and r.get("classif2") != currency:
            continue
        if r["obs_value"] and r["time"].isdigit():
            out[int(r["time"])] = float(r["obs_value"])
    return out


def main():
    tables = {name: rows(ONET / (name + ".csv")) for name in
              ["occupation_data", "career_interest_types", "abilities", "knowledge", "essential_skills", "transferable_skills", "work_styles"]}
    bls = json.loads((ROOT / "frontend/lib/data/bls-2025.json").read_text(encoding="utf-8"))
    occupations = {}
    pk_earnings_major_groups = {str(group): ilo_series(ROOT / "data/ilo-pak-earnings.csv", str(group), "OCU_ISCO08_", "CUR_TYPE_LCU").get(2025) for group in range(1, 10)}
    if any(value is None for value in pk_earnings_major_groups.values()):
        raise ValueError("Incomplete Pakistan major-group earnings for 2025")
    for career, soc in SOC.items():
        info = next((r for r in tables["occupation_data"] if r["O*NET-SOC Code"] == soc), None)
        if not info:
            raise ValueError(f"O*NET occupation missing: {soc}")
        interests = {r["Element Name"]: float(r["Data Value"]) for r in tables["career_interest_types"]
                     if r["O*NET-SOC Code"] == soc and r["Scale ID"] == "OI" and r["Data Value"]}
        if set(interests) != {"Realistic", "Investigative", "Artistic", "Social", "Enterprising", "Conventional"}:
            raise ValueError(f"Incomplete RIASEC profile: {soc}: {interests}")
        requirements = {}
        for dim, elements in CROSSWALK.items():
            vals = [onet_value(tables[table], soc, element, "WI" if table == "work_styles" else "IM") for table, element in elements]
            vals = [(v + 3) / 6 if table == "work_styles" else (v - 1) / 4
                    for (table, _), v in zip(elements, vals) if v is not None]
            if vals:
                requirements[dim] = round(sum(vals) / len(vals), 4)
        if set(requirements) != set(CROSSWALK):
            raise ValueError(f"Incomplete O*NET 31.0 crosswalk for {soc}: {set(CROSSWALK) - set(requirements)}")
        keywords = sorted(
            [(r["Element Name"], float(r["Data Value"])) for name in ("knowledge", "essential_skills", "transferable_skills")
             for r in tables[name] if r["O*NET-SOC Code"] == soc and r["Scale ID"] == "IM" and r["Data Value"]],
            key=lambda pair: pair[1], reverse=True,
        )[:12]
        code = ISCO2[career]
        employment = ilo_series(ROOT / "data/ilo-pak-isco2.csv", code, "OC2_ISCO08_")
        earnings = ilo_series(ROOT / "data/ilo-pak-earnings.csv", code[0], "OCU_ISCO08_", "CUR_TYPE_LCU")
        pak = {
            "isco2_proxy": code,
            "employment_thousands_2025": employment.get(2025),
            "employment_thousands_2021": employment.get(2021),
            "median_hourly_pkr_2025_major_group": earnings.get(2025),
        }
        if not all(v is not None for k, v in pak.items() if k != "isco2_proxy"):
            raise ValueError(f"Missing 2021/2025 ILOSTAT observations for {career}: {pak}")
        occupations[career] = {
            "soc": soc, "title": info["Title"], "description": info["Description"],
            "interests": interests, "requirements": requirements,
            "keywords": [name for name, _ in keywords],
            "us": bls["occupations"][career], "pk": pak,
        }
    payload = {
        "onet_release": "31.0", "bls_wage_year": 2025, "bls_projection": "2025-2035",
        "ilo_years": [2021, 2025], "pk_earnings_major_groups_2025": pk_earnings_major_groups,
        "sources": {
            "onet": "https://www.onetcenter.org/database.html",
            "bls_employment": "https://www.bls.gov/emp/tables/occupational-separations-and-openings.htm",
            "bls_wages": "https://www.bls.gov/oes/tables.htm",
            "ilo_employment": "https://rplumber.ilo.org/data/indicator?id=EMP_TEMP_SEX_OC2_NB&ref_area=PAK",
            "ilo_earnings": "https://rplumber.ilo.org/data/indicator?id=EAR_EHRM_SEX_OCU_CUR_NB&ref_area=PAK",
        },
        "numbeo_context": {
            "period": "2026 Mid-Year", "index": {"US": 54.8, "PK": 12.4},
            "source": "https://www.numbeo.com/cost-of-living/rankings_by_country.jsp?displayColumn=2",
            "note": "Cost of Living Plus Rent Index; context only, not used in within-country career ranking",
        },
        "occupations": occupations,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(occupations)} sourced occupations to {OUT}")


if __name__ == "__main__":
    main()
