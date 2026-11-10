
from pathlib import Path
import pandas as pd

# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "dengue"
    / "dengue_cases_2025_2026.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = (
    OUTPUT_DIR / "dengue_weekly_25_areas_2025_2026.csv"
)

# --------------------------------------------------
# 2. LOAD DATA
# --------------------------------------------------

print("\nRISKWEAVE DENGUE DATA PREPARATION")
print("=" * 55)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input file not found: {INPUT_FILE}\n"
        "Place dengue_cases_2025_2026.csv inside "
        "data/raw/dengue/"
    )

df = pd.read_csv(INPUT_FILE)

required_columns = [
    "year",
    "week",
    "district",
    "weekly_cases",
    "cumulative_cases",
]

missing_columns = [
    col for col in required_columns if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )

print("Original records:", len(df))
print("Years:", sorted(df["year"].unique()))

# --------------------------------------------------
# 3. CLEAN DISTRICT NAMES
# --------------------------------------------------

df["district"] = (
    df["district"]
    .astype(str)
    .str.strip()
    .str.lower()
)

district_mapping = {
    "ampara": "ampara",
    "kalmunai": "ampara",
    "anuradhapura": "anuradhapura",
    "badulla": "badulla",
    "batticaloa": "batticaloa",
    "colombo": "colombo",
    "galle": "galle",
    "gampaha": "gampaha",
    "hambantota": "hambantota",
    "jaffna": "jaffna",
    "kalutara": "kalutara",
    "kandy": "kandy",
    "kegalle": "kegalle",
    "kilinochchi": "kilinochchi",
    "kurunegala": "kurunegala",
    "mannar": "mannar",
    "matale": "matale",
    "matara": "matara",
    "monaragala": "moneragala",
    "moneragala": "moneragala",
    "mullaitivu": "mullaitivu",
    "nuwara eliya": "nuwaraeliya",
    "polonnaruwa": "polonnaruwa",
    "puttalam": "puttalam",
    "ratnapura": "ratnapura",
    "trincomalee": "trincomalee",
    "vavuniya": "vavuniya",
}

unknown_districts = sorted(
    set(df["district"]) - set(district_mapping)
)

if unknown_districts:
    raise ValueError(
        f"Unknown district names: {unknown_districts}"
    )

df["district_key"] = df["district"].map(district_mapping)

# --------------------------------------------------
# 4. VALIDATE CASE COUNTS
# --------------------------------------------------


# --------------------------------------------------
# 4. VALIDATE CASE COUNTS
# --------------------------------------------------

df["year"] = pd.to_numeric(
    df["year"], errors="raise"
).astype(int)

df["week"] = pd.to_numeric(
    df["week"], errors="raise"
).astype(int)

df["weekly_cases"] = pd.to_numeric(
    df["weekly_cases"], errors="raise"
)

if (df["weekly_cases"] < 0).any():
    raise ValueError("Negative weekly dengue cases found.")

# Check duplicates using ORIGINAL district names.
# Ampara and Kalmunai are separate source areas.
if df.duplicated(
    ["year", "week", "district"]
).any():
    raise ValueError(
        "Duplicate original district-week records found."
    )

print("Original district-week duplicate check passed.")


# --------------------------------------------------
# 5. AGGREGATE TO 25 RISKWEAVE AREAS
# --------------------------------------------------

weekly = (
    df.groupby(
        ["year", "week", "district_key"],
        as_index=False
    )
    .agg(
        weekly_cases=("weekly_cases", "sum"),
        source_reporting_rows=("district", "count"),
        source_areas=(
            "district",
            lambda x: ";".join(sorted(x.unique()))
        )
    )
)

# --------------------------------------------------
# 6. VALIDATE 25 AREAS PER WEEK
# --------------------------------------------------

area_counts = weekly.groupby(
    ["year", "week"]
)["district_key"].nunique()

invalid_weeks = area_counts[area_counts != 25]

if not invalid_weeks.empty:
    raise ValueError(
        "Some weeks do not contain exactly 25 RiskWeave areas:\n"
        f"{invalid_weeks}"
    )

expected_districts = set(district_mapping.values())

for (year, week), group in weekly.groupby(["year", "week"]):
    actual = set(group["district_key"])

    if actual != expected_districts:
        raise ValueError(
            f"District mismatch in {year}, Week {week}"
        )

    
# --------------------------------------------------
# 5B. ADD OFFICIAL 2026 WEEK 44 DATA
# --------------------------------------------------

week44_cases = {
    "ampara": 83,
    "anuradhapura": 19,
    "badulla": 18,
    "batticaloa": 14,
    "colombo": 262,
    "galle": 80,
    "gampaha": 227,
    "hambantota": 23,
    "jaffna": 24,
    "kalutara": 64,
    "kandy": 219,
    "kegalle": 44,
    "kilinochchi": 0,
    "kurunegala": 30,
    "mannar": 3,
    "matale": 54,
    "matara": 32,
    "moneragala": 15,
    "mullaitivu": 2,
    "nuwaraeliya": 36,
    "polonnaruwa": 1,
    "puttalam": 10,
    "ratnapura": 49,
    "trincomalee": 12,
    "vavuniya": 4,
}

if ((weekly["year"] == 2026) & (weekly["week"] == 44)).any():
    raise ValueError("2026 Week 44 already exists.")

week44 = pd.DataFrame({
    "year": 2026,
    "week": 44,
    "district_key": list(week44_cases.keys()),
    "weekly_cases": list(week44_cases.values()),
    "source_reporting_rows": [
        2 if district == "ampara" else 1
        for district in week44_cases
    ],
    "source_areas": [
        "Ampara;Kalmunai" if district == "ampara"
        else district
        for district in week44_cases
    ],
})

assert week44["weekly_cases"].sum() == 1325

weekly = pd.concat(
    [weekly, week44],
    ignore_index=True
)

print("2026 Week 44 added successfully.")
print("Week 44 cases:", week44["weekly_cases"].sum())


# --------------------------------------------------
# 7. SORT AND SAVE
# --------------------------------------------------

weekly = weekly.sort_values(
    ["year", "week", "district_key"]
).reset_index(drop=True)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

weekly.to_csv(OUTPUT_FILE, index=False)

# --------------------------------------------------
# 8. SUMMARY
# --------------------------------------------------

print("\nDATA PREPARATION COMPLETED")
print("=" * 55)

print("Original reporting areas:", df["district"].nunique())
print("RiskWeave reporting areas:", weekly["district_key"].nunique())
print("Prepared records:", len(weekly))

print("\nWeekly coverage:")

print(
    weekly.groupby("year")["week"]
    .agg(["min", "max", "nunique"])
)

print("\n2026 latest available week:")
print(weekly.loc[weekly["year"] == 2026, "week"].max())

print("\nOutput saved:")
print(OUTPUT_FILE)

print("\nOriginal input file was not modified.")
