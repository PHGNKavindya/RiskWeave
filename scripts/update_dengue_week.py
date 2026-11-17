"""
RiskWeave - Weekly Dengue CSV Updater
=====================================

Input:
    data/input/dengue_weekly/

Master:
    data/raw/dengue/dengue_cases_2025_2026.csv

Run from project root:
    python scripts/update_dengue_week.py

For a specific file:
    python scripts/update_dengue_week.py --input data/input/dengue_weekly/dengue_2026_week_44.csv

For an official correction:
    python scripts/update_dengue_week.py --replace

Required input columns:
    year
    week
    district
    weekly_cases
    cumulative_cases
    source_pdf

Rules:
    1. Retain all historical records.
    2. Support all 25 Sri Lankan districts.
    3. Combine Kalmunai with Ampara.
    4. Prevent duplicate district-week records.
    5. Replace an existing week only with --replace.
    6. Create a backup before modifying the master CSV.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "input"
    / "dengue_weekly"
)

MASTER_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "dengue"
    / "dengue_cases_2025_2026.csv"
)

REQUIRED_COLUMNS = [
    "year",
    "week",
    "district",
    "weekly_cases",
    "cumulative_cases",
    "source_pdf",
]


# ============================================================
# 2. OFFICIAL DISTRICTS
# ============================================================

DISTRICTS_25 = [
    "Ampara",
    "Anuradhapura",
    "Badulla",
    "Batticaloa",
    "Colombo",
    "Galle",
    "Gampaha",
    "Hambantota",
    "Jaffna",
    "Kalutara",
    "Kandy",
    "Kegalle",
    "Kilinochchi",
    "Kurunegala",
    "Mannar",
    "Matale",
    "Matara",
    "Monaragala",
    "Mullaitivu",
    "Nuwara Eliya",
    "Polonnaruwa",
    "Puttalam",
    "Ratnapura",
    "Trincomalee",
    "Vavuniya",
]

ALIASES = {
    "kalmunai": "Ampara",
    "ampara": "Ampara",
}


# ============================================================
# 3. DISTRICT NORMALIZATION
# ============================================================

def normalize_district(value: object) -> str:

    name = " ".join(str(value).strip().split())

    key = name.casefold()

    if key in ALIASES:
        return ALIASES[key]

    for district in DISTRICTS_25:

        if key == district.casefold():
            return district

    return name


# ============================================================
# 4. VALIDATE AND STANDARDIZE DATA
# ============================================================

def validate_and_standardize(
    df: pd.DataFrame,
    label: str
) -> pd.DataFrame:

    print(f"\nValidating {label}...")

    missing = set(REQUIRED_COLUMNS) - set(df.columns)

    if missing:

        raise ValueError(
            f"{label} is missing columns: {sorted(missing)}"
        )

    df = df[REQUIRED_COLUMNS].copy()

    # Convert numeric columns
    numeric_columns = [
        "year",
        "week",
        "weekly_cases",
        "cumulative_cases",
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="raise"
        )

        if df[col].isna().any():

            raise ValueError(
                f"{label}: {col} contains missing values."
            )

        if not (df[col] % 1 == 0).all():

            raise ValueError(
                f"{label}: {col} must contain whole numbers."
            )

        df[col] = df[col].astype("int64")

    # Validate year and week
    if (df["year"] < 2000).any():

        raise ValueError(
            f"{label}: Invalid year detected."
        )

    if not df["week"].between(1, 53).all():

        raise ValueError(
            f"{label}: Week must be between 1 and 53."
        )

    # Validate case counts
    if (
        df[["weekly_cases", "cumulative_cases"]] < 0
    ).any().any():

        raise ValueError(
            f"{label}: Case counts cannot be negative."
        )

    # Normalize districts
    df["district"] = df["district"].map(
        normalize_district
    )

    df["source_pdf"] = (
        df["source_pdf"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Identify invalid districts
    unknown = sorted(
        set(df["district"]) - set(DISTRICTS_25)
    )

    if unknown:

        raise ValueError(
            f"{label}: Unknown districts: {unknown}"
        )

    # Combine Kalmunai with Ampara
    df = (
        df.groupby(
            ["year", "week", "district"],
            as_index=False
        )
        .agg(
            weekly_cases=("weekly_cases", "sum"),
            cumulative_cases=("cumulative_cases", "sum"),
            source_pdf=("source_pdf", "first"),
        )
    )

    return df[REQUIRED_COLUMNS].copy()


# ============================================================
# 5. SELECT WEEKLY INPUT CSV
# ============================================================

def choose_input(
    explicit_input: str | None
) -> Path:

    if explicit_input:

        path = Path(explicit_input)

        if not path.is_absolute():

            path = PROJECT_ROOT / path

        return path

    if not INPUT_DIR.exists():

        raise FileNotFoundError(
            f"Input directory not found: {INPUT_DIR}"
        )

    candidates = sorted(
        INPUT_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not candidates:

        raise FileNotFoundError(
            f"No weekly CSV found in {INPUT_DIR}"
        )

    if len(candidates) > 1:

        print("\nAvailable weekly CSV files:")

        for item in candidates:

            print("  ", item.name)

        print(
            "\nUsing newest file:",
            candidates[0].name
        )

    return candidates[0]


# ============================================================
# 6. VERIFY WEEKLY INPUT
# ============================================================

def validate_weekly_input(
    weekly: pd.DataFrame
) -> tuple[int, int]:

    periods = (
        weekly[["year", "week"]]
        .drop_duplicates()
    )

    if len(periods) != 1:

        raise ValueError(
            "Weekly input must contain exactly one "
            "year/week reporting period."
        )

    year = int(periods.iloc[0]["year"])

    week = int(periods.iloc[0]["week"])

    districts = set(weekly["district"])

    if (
        len(weekly) != 25
        or districts != set(DISTRICTS_25)
    ):

        missing = sorted(
            set(DISTRICTS_25) - districts
        )

        raise ValueError(
            "Weekly report must contain all 25 districts.\n"
            f"Found rows: {len(weekly)}\n"
            f"Missing districts: {missing}"
        )

    return year, week


# ============================================================
# 7. UPDATE MASTER DATASET
# ============================================================

def update_master(
    input_path: Path,
    replace_existing: bool = False
) -> None:

    print("\n" + "=" * 60)
    print("RISKWEAVE WEEKLY DENGUE DATA UPDATE")
    print("=" * 60)

    # Check input file
    if not input_path.exists():

        raise FileNotFoundError(
            f"Weekly input CSV not found: {input_path}"
        )

    # Check master file
    if not MASTER_PATH.exists():

        raise FileNotFoundError(
            f"Master dataset not found: {MASTER_PATH}"
        )

    # --------------------------------------------------------
    # Read weekly report
    # --------------------------------------------------------

    print("\nReading weekly report...")

    weekly_raw = pd.read_csv(input_path)

    print(
        "Weekly input records:",
        len(weekly_raw)
    )

    weekly = validate_and_standardize(
        weekly_raw,
        "Weekly input"
    )

    year, week = validate_weekly_input(weekly)

    # --------------------------------------------------------
    # Read historical master dataset
    # --------------------------------------------------------

    print("\nReading historical master dataset...")

    master_raw = pd.read_csv(MASTER_PATH)

    print(
        "Existing master records:",
        len(master_raw)
    )

    master = validate_and_standardize(
        master_raw,
        "Master dataset"
    )

    # --------------------------------------------------------
    # Check reporting period
    # --------------------------------------------------------

    period_mask = (
        (master["year"] == year)
        & (master["week"] == week)
    )

    exists = period_mask.any()

    if exists and not replace_existing:

        raise ValueError(
            f"\n{year} Week {week} already exists "
            "in the historical dataset.\n"
            "Use --replace only if this is an official correction."
        )

    if exists and replace_existing:

        print(
            f"\nReplacing existing {year} Week {week}..."
        )

        master = master.loc[
            ~period_mask
        ].copy()

    else:

        print(
            f"\nAdding new reporting period: "
            f"{year} Week {week}"
        )

    # --------------------------------------------------------
    # Append new weekly records
    # --------------------------------------------------------

    updated = pd.concat(
        [master, weekly],
        ignore_index=True
    )

    updated = updated.sort_values(
        ["year", "week", "district"]
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # Check duplicates
    # --------------------------------------------------------

    duplicates = updated.duplicated(
        subset=["year", "week", "district"]
    )

    if duplicates.any():

        raise ValueError(
            "Duplicate district-week records detected."
        )

    # --------------------------------------------------------
    # Check historical district coverage
    # --------------------------------------------------------

    period_counts = (
        updated.groupby(["year", "week"])
        .size()
    )

    invalid_periods = period_counts[
        period_counts != 25
    ]

    if not invalid_periods.empty:

        raise ValueError(
            "Some historical reporting periods do not "
            "contain exactly 25 districts:\n"
            f"{invalid_periods.to_dict()}"
        )

    # --------------------------------------------------------
    # Create backup
    # --------------------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = MASTER_PATH.with_name(
        f"{MASTER_PATH.stem}_backup_{timestamp}"
        f"{MASTER_PATH.suffix}"
    )

    shutil.copy2(
        MASTER_PATH,
        backup_path
    )

    # --------------------------------------------------------
    # Save updated master dataset
    # --------------------------------------------------------

    temp_path = MASTER_PATH.with_name(
        MASTER_PATH.name + ".tmp"
    )

    try:

        updated.to_csv(
            temp_path,
            index=False
        )

        temp_path.replace(MASTER_PATH)

    except Exception:

        if temp_path.exists():
            temp_path.unlink()

        raise

    # --------------------------------------------------------
    # Display update summary
    # --------------------------------------------------------

    weekly_total = int(
        weekly["weekly_cases"].sum()
    )

    master_total = int(
        updated["weekly_cases"].sum()
    )

    latest_period = (
        updated[["year", "week"]]
        .drop_duplicates()
        .sort_values(["year", "week"])
        .iloc[-1]
    )

    print("\n" + "=" * 60)
    print("WEEKLY DENGUE DATA UPDATE SUCCESSFUL")
    print("=" * 60)

    print(f"\nInput report       : {input_path.name}")

    print(f"Reporting period   : {year} Week {week}")

    print(f"Districts          : {len(weekly)}")

    print(f"Weekly cases       : {weekly_total:,}")

    print(f"Total master rows  : {len(updated):,}")

    print(f"Total historical cases: {master_total:,}")

    print(
        f"Latest master week : "
        f"{int(latest_period['year'])} "
        f"Week {int(latest_period['week'])}"
    )

    print(f"\nUpdated master     : {MASTER_PATH}")

    print(f"Backup created     : {backup_path}")

    print("\nAll validation checks passed.")

    print("=" * 60)


# ============================================================
# 8. MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "RiskWeave weekly dengue CSV updater"
        )
    )

    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Specific weekly dengue CSV file."
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Replace an existing reporting week "
            "for an official correction."
        )
    )

    args = parser.parse_args()

    input_path = choose_input(
        args.input
    )

    update_master(
        input_path=input_path,
        replace_existing=args.replace
    )


if __name__ == "__main__":

    main()