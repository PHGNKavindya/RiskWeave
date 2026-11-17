"""
RiskWeave weekly dengue CSV updater.

Default project paths:
  New weekly reports: data/input/dengue_weekly/
  Master dataset:     data/raw/dengue/dengue_cases_2025_2026.csv

Run from the RiskWeave project root:
  python scripts/update_dengue_week.py

Optional:
  python scripts/update_dengue_week.py --input data/input/dengue_weekly/dengue_2026_week_44.csv
  python scripts/update_dengue_week.py --replace

The uploaded weekly CSV must contain:
  year, week, district, weekly_cases, cumulative_cases, source_pdf

Kalmunai is combined with Ampara. Official weekly and cumulative values
are summed for those two rows. Existing historical weeks are retained.
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "data" / "input" / "dengue_weekly"
MASTER_PATH = (
    PROJECT_ROOT / "data" / "raw" / "dengue" /
    "dengue_cases_2025_2026.csv"
)

REQUIRED_COLUMNS = {
    "year", "week", "district", "weekly_cases",
    "cumulative_cases", "source_pdf"
}

DISTRICTS_25 = [
    "Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo",
    "Galle", "Gampaha", "Hambantota", "Jaffna", "Kalutara",
    "Kandy", "Kegalle", "Kilinochchi", "Kurunegala", "Mannar",
    "Matale", "Matara", "Monaragala", "Mullaitivu", "Nuwara Eliya",
    "Polonnaruwa", "Puttalam", "Ratnapura", "Trincomalee", "Vavuniya",
]

ALIASES = {"kalmunai": "Ampara", "ampara": "Ampara"}


def normalize_district(value: object) -> str:
    name = " ".join(str(value).strip().split())
    key = name.casefold()
    if key in ALIASES:
        return ALIASES[key]
    for official_name in DISTRICTS_25:
        if key == official_name.casefold():
            return official_name
    return name


def validate_and_standardize(df: pd.DataFrame, label: str) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {sorted(missing)}")

    df = df[list(REQUIRED_COLUMNS)].copy()
    for col in ["year", "week", "weekly_cases", "cumulative_cases"]:
        df[col] = pd.to_numeric(df[col], errors="raise")

        if df[col].isna().any():
            raise ValueError(f"{label}: {col} contains missing values.")
        if (df[col] % 1 != 0).any():
            raise ValueError(f"{label}: {col} must contain whole numbers.")
        df[col] = df[col].astype("int64")

    if not df["week"].between(1, 53).all():
        raise ValueError(f"{label}: week values must be between 1 and 53.")
    if (df[["weekly_cases", "cumulative_cases"]] < 0).any().any():
        raise ValueError(f"{label}: case counts cannot be negative.")

    df["district"] = df["district"].map(normalize_district)
    df["source_pdf"] = df["source_pdf"].fillna("").astype(str).str.strip()

    unknown = sorted(set(df["district"]) - set(DISTRICTS_25))
    if unknown:
        raise ValueError(f"{label}: unrecognized district names: {unknown}")

    # Combine Ampara + Kalmunai. Both weekly and cumulative official counts
    # are additive when the two source rows represent the same reporting week.
    df = (
        df.groupby(["year", "week", "district"], as_index=False)
          .agg(
              weekly_cases=("weekly_cases", "sum"),
              cumulative_cases=("cumulative_cases", "sum"),
              source_pdf=("source_pdf", "first"),
          )
    )
    return df[
        ["year", "week", "district", "weekly_cases",
         "cumulative_cases", "source_pdf"]
    ]


def choose_input(explicit_input: str | None) -> Path:
    if explicit_input:
        path = Path(explicit_input)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    candidates = sorted(
        INPUT_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No weekly CSV found in {INPUT_DIR}. "
            "Copy the new report CSV into this folder first."
        )
    if len(candidates) > 1:
        print("CSV files found (newest first):")
        for item in candidates:
            print(f"  - {item.name}")
        print(f"Using newest file: {candidates[0].name}")
    return candidates[0]


def update_master(input_path: Path, replace_existing: bool) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"Weekly input CSV not found: {input_path}")
    if not MASTER_PATH.exists():
        raise FileNotFoundError(
            f"Master CSV not found: {MASTER_PATH}. "
            "Check that your existing historical file is in data/raw/dengue/."
        )

    weekly_raw = pd.read_csv(input_path)
    weekly = validate_and_standardize(weekly_raw, "Weekly input")

    periods = weekly[["year", "week"]].drop_duplicates()
    if len(periods) != 1:
        raise ValueError("Weekly input must contain exactly one year/week period.")

    year = int(periods.iloc[0]["year"])
    week = int(periods.iloc[0]["week"])

    districts = set(weekly["district"])
    if len(weekly) != 25 or districts != set(DISTRICTS_25):
        missing = sorted(set(DISTRICTS_25) - districts)
        raise ValueError(
            f"Weekly report must contain all 25 districts after combining "
            f"Kalmunai with Ampara. Found {len(weekly)} rows. Missing: {missing}"
        )

    master_raw = pd.read_csv(MASTER_PATH)
    master = validate_and_standardize(master_raw, "Master dataset")

    period_mask = (master["year"] == year) & (master["week"] == week)
    exists = period_mask.any()
    if exists and not replace_existing:
        raise ValueError(
            f"{year} week {week} already exists in the master dataset. "
            "If this is an official correction, rerun with --replace."
        )

    if exists:
        master = master.loc[~period_mask].copy()

    updated = pd.concat([master, weekly], ignore_index=True)
    updated = updated.sort_values(
        ["year", "week", "district"]
    ).reset_index(drop=True)

    # Final integrity checks across the complete dataset.
    dup = updated.duplicated(["year", "week", "district"])
    if dup.any():
        raise ValueError("Duplicate year-week-district records detected.")

    counts = updated.groupby(["year", "week"]).size()
    if not (counts == 25).all():
        bad_periods = counts[counts != 25].to_dict()
        raise ValueError(
            "Some historical periods do not contain exactly 25 districts "
            f"after combining Kalmunai and Ampara: {bad_periods}"
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = MASTER_PATH.with_name(
        f"{MASTER_PATH.stem}_backup_{timestamp}{MASTER_PATH.suffix}"
    )
    shutil.copy2(MASTER_PATH, backup)

    temp = MASTER_PATH.with_suffix(".csv.tmp")
    updated.to_csv(temp, index=False)
    temp.replace(MASTER_PATH)

    week_total = int(weekly["weekly_cases"].sum())
    print("\nWEEKLY DENGUE DATA UPDATE SUCCESSFUL")
    print(f"Input report      : {input_path.name}")
    print(f"Reporting period  : {year}, week {week}")
    print(f"Districts         : {len(weekly)}")
    print(f"Weekly cases total: {week_total:,}")
    print(f"Master records    : {len(updated):,}")
    print(f"Updated master    : {MASTER_PATH}")
    print(f"Backup created    : {backup}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update the RiskWeave master dengue CSV from a weekly report."
    )
    parser.add_argument(
        "--input",
        help="Optional weekly CSV path. Without this, newest CSV in data/input/dengue_weekly is used.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace a week already in the master dataset (for official corrections only).",
    )
    args = parser.parse_args()

    input_path = choose_input(args.input)
    update_master(input_path, args.replace)


if __name__ == "__main__":
    main()
