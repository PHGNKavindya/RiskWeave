
from pathlib import Path
from datetime import datetime
import shutil

import pandas as pd


# ============================================================
# 1. PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DENGUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dengue_weekly_25_districts.csv"
)

BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


# ============================================================
# 2. OFFICIAL WEEK 44 CASE COUNTS
# Reporting period: 26 October - 1 November 2026
# ============================================================

WEEK_START = pd.Timestamp("2026-10-26")
WEEK_END = pd.Timestamp("2026-11-01")

WEEK44_CASES = {
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

EXPECTED_TOTAL = 1325


# ============================================================
# 3. VALIDATE SOURCE COUNTS
# ============================================================

def validate_new_data():

    total = sum(WEEK44_CASES.values())

    if len(WEEK44_CASES) != 25:
        raise ValueError(
            f"Expected 25 reporting areas, got {len(WEEK44_CASES)}"
        )

    if total != EXPECTED_TOTAL:
        raise ValueError(
            f"Case total mismatch: {total}, expected {EXPECTED_TOTAL}"
        )

    if (WEEK_END - WEEK_START).days != 6:
        raise ValueError("Reporting period must cover seven days.")

    print("New dengue data validation passed.")
    print("Reporting areas:", len(WEEK44_CASES))
    print("Total cases:", total)


# ============================================================
# 4. LOAD EXISTING DATA
# ============================================================

def load_existing_data():

    if not DENGUE_FILE.exists():
        raise FileNotFoundError(DENGUE_FILE)

    dengue = pd.read_csv(DENGUE_FILE)

    dengue["week_start"] = pd.to_datetime(
        dengue["week_start"]
    )

    dengue["week_end"] = pd.to_datetime(
        dengue["week_end"]
    )

    return dengue


# ============================================================
# 5. CHECK DISTRICT COMPATIBILITY
# ============================================================

def validate_districts(dengue):

    existing_districts = set(
        dengue["district_key"].astype(str).str.lower()
    )

    new_districts = set(WEEK44_CASES.keys())

    if existing_districts != new_districts:

        missing = new_districts - existing_districts
        extra = existing_districts - new_districts

        raise ValueError(
            f"District mismatch.\n"
            f"Missing from historical data: {missing}\n"
            f"Extra in historical data: {extra}"
        )


# ============================================================
# 6. PREPARE NEW RECORDS
# ============================================================

def prepare_new_records(dengue):

    rows = []

    for district, cases in WEEK44_CASES.items():

        # The official report has 26 reporting divisions.
        # Ampara and Kalmunai are combined into one model area.
        source_rows = 2 if district == "ampara" else 1

        source_areas = (
            "Ampara;Kalmunai"
            if district == "ampara"
            else district.title()
        )

        rows.append({
            "district_key": district,
            "week_start": WEEK_START,
            "week_end": WEEK_END,
            "dengue_cases": cases,
            "reporting_period_days": 7,
            "source_reporting_rows": source_rows,
            "source_areas": source_areas,
        })

    new_data = pd.DataFrame(rows)

    # Preserve the original dataset's column structure.
    new_data = new_data.reindex(
        columns=dengue.columns
    )

    return new_data


# ============================================================
# 7. BACKUP AND UPDATE DATASET
# ============================================================

def update_dataset():

    dengue = load_existing_data()

    validate_districts(dengue)

    # Prevent duplicate updates.
    existing_period = dengue[
        dengue["week_start"] == WEEK_START
    ]

    if not existing_period.empty:

        raise ValueError(
            "Week 44, 2026 already exists in the dataset. "
            "No changes were made."
        )

    latest_historical_date = dengue["week_start"].max()

    if WEEK_START <= latest_historical_date:

        raise ValueError(
            "New reporting period is not later than existing data."
        )

    new_data = prepare_new_records(dengue)

    updated = pd.concat(
        [dengue, new_data],
        ignore_index=True
    )

    updated = updated.sort_values(
        ["district_key", "week_start"]
    ).reset_index(drop=True)

    # Create backup before modifying original dataset.
    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    backup_file = (
        BACKUP_DIR
        / f"dengue_weekly_backup_{datetime.now():%Y%m%d_%H%M%S}.csv"
    )

    shutil.copy2(DENGUE_FILE, backup_file)

    # Save updated dataset.
    updated.to_csv(DENGUE_FILE, index=False)

    return updated, backup_file


# ============================================================
# 8. MAIN
# ============================================================

def main():

    print("\nRISKWEAVE DENGUE DATA UPDATE")
    print("=" * 45)

    validate_new_data()

    updated, backup_file = update_dataset()

    latest = updated[
        updated["week_start"] == WEEK_START
    ]

    print("\nUPDATE COMPLETED")
    print("-" * 45)

    print("Reporting period:", WEEK_START.date(), "to", WEEK_END.date())
    print("New district records:", len(latest))
    print("New cases:", latest["dengue_cases"].sum())
    print("Total dataset records:", len(updated))
    print("Latest period in dataset:", updated["week_start"].max().date())

    print("\nBACKUP CREATED")
    print(backup_file)

    print("\nWEEK 44 DISTRICT CASES")
    print(
        latest[
            ["district_key", "dengue_cases"]
        ].to_string(index=False)
    )

    print("\nIMPORTANT:")
    print(
        "Official dates are preserved as Monday-Sunday. "
        "Do not run the prediction pipeline until weekly "
        "period alignment has been checked."
    )


if __name__ == "__main__":
    main()
