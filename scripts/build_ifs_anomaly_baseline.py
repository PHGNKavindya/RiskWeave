
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "environmental_anomalies"
    / "ifs_baseline_2017_2023"
    / "ifs_baseline_2017_2023.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "environmental_anomalies"
    / "ifs_baseline_2017_2023"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_FILE = (
    OUTPUT_DIR
    / "ifs_district_monthly_baselines_2017_2023.csv"
)

COVERAGE_FILE = (
    OUTPUT_DIR
    / "ifs_baseline_group_coverage_2017_2023.csv"
)

# ============================================================
# 2. CONFIGURATION
# ============================================================

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

LOWER_QUANTILE = 0.01
UPPER_QUANTILE = 0.99

MIN_VALID_OBSERVATIONS = 100

EXPECTED_DISTRICTS = 25
EXPECTED_GROUPS = EXPECTED_DISTRICTS * 12

# ============================================================
# 3. LOAD DATA
# ============================================================

print("\n" + "=" * 65)
print("IFS ANOMALY BASELINE CONSTRUCTION")
print("=" * 65)

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Input dataset not found: {INPUT_FILE}"
    )

df = pd.read_csv(
    INPUT_FILE,
    parse_dates=["date"]
)

print("\nDataset shape:", df.shape)

# ============================================================
# 4. DATA VALIDATION
# ============================================================

required_columns = [
    "district",
    "date"
] + VARIABLES

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing columns: {missing_columns}"
    )

df["district"] = df["district"].astype(str).str.strip()

for variable in VARIABLES:
    df[variable] = pd.to_numeric(
        df[variable],
        errors="coerce"
    )

if df["date"].isna().any():
    raise ValueError("Invalid dates found.")

if df.duplicated(["district", "date"]).any():
    raise ValueError("Duplicate district-date records found.")

if df["district"].nunique() != EXPECTED_DISTRICTS:
    raise ValueError("Unexpected district count.")

if df["date"].min() != pd.Timestamp("2017-01-01"):
    raise ValueError("Unexpected baseline start date.")

if df["date"].max() != pd.Timestamp("2023-12-31"):
    raise ValueError("Unexpected baseline end date.")

# Create calendar month.
df["month"] = df["date"].dt.month

print("Districts:", df["district"].nunique())
print("Date coverage:", df["date"].min(), "to", df["date"].max())

# ============================================================
# 5. CALCULATE DISTRICT-MONTH THRESHOLDS
# ============================================================

print("\nCalculating district-month thresholds...")

baseline_rows = []
coverage_rows = []

for (district, month), group in df.groupby(
    ["district", "month"],
    sort=True
):

    baseline_row = {
        "district": district,
        "month": int(month),
        "total_days": len(group)
    }

    coverage_row = {
        "district": district,
        "month": int(month),
        "total_days": len(group)
    }

    for variable in VARIABLES:

        valid_values = group[variable].dropna()

        valid_count = len(valid_values)

        coverage_percentage = (
            valid_count / len(group) * 100
        )

        coverage_row[
            f"{variable}_valid_count"
        ] = valid_count

        coverage_row[
            f"{variable}_missing_count"
        ] = int(group[variable].isna().sum())

        coverage_row[
            f"{variable}_coverage_pct"
        ] = round(coverage_percentage, 2)

        baseline_row[
            f"{variable}_valid_count"
        ] = valid_count

        if valid_count < MIN_VALID_OBSERVATIONS:

            raise ValueError(
                f"Insufficient observations for "
                f"{district}, month {month}, {variable}: "
                f"{valid_count}"
            )

        baseline_row[
            f"{variable}_q01"
        ] = valid_values.quantile(
            LOWER_QUANTILE
        )

        baseline_row[
            f"{variable}_q99"
        ] = valid_values.quantile(
            UPPER_QUANTILE
        )

    baseline_rows.append(baseline_row)
    coverage_rows.append(coverage_row)

# ============================================================
# 6. CREATE OUTPUT DATAFRAMES
# ============================================================

baseline_df = pd.DataFrame(baseline_rows)

coverage_df = pd.DataFrame(coverage_rows)

baseline_df = baseline_df.sort_values(
    ["district", "month"]
).reset_index(drop=True)

coverage_df = coverage_df.sort_values(
    ["district", "month"]
).reset_index(drop=True)

# ============================================================
# 7. VALIDATE BASELINE
# ============================================================

print("\n" + "=" * 65)
print("BASELINE VALIDATION")
print("=" * 65)

print("Expected groups:", EXPECTED_GROUPS)
print("Actual groups:", len(baseline_df))

print(
    "Duplicate district-month groups:",
    baseline_df.duplicated(
        ["district", "month"]
    ).sum()
)

print("\nBaseline columns:")
print(baseline_df.columns.tolist())

threshold_columns = [
    f"{variable}_{suffix}"
    for variable in VARIABLES
    for suffix in ["q01", "q99"]
]

print("\nMissing threshold values:")
print(
    baseline_df[threshold_columns].isna().sum()
)

# Check threshold ordering.
for variable in VARIABLES:

    invalid_thresholds = (
        baseline_df[f"{variable}_q01"]
        >
        baseline_df[f"{variable}_q99"]
    ).sum()

    print(
        f"{variable} invalid threshold pairs:",
        invalid_thresholds
    )

    if invalid_thresholds > 0:
        raise ValueError(
            f"Invalid threshold ordering for {variable}"
        )

if len(baseline_df) != EXPECTED_GROUPS:
    raise ValueError("Incorrect number of baseline groups.")

if baseline_df.duplicated(
    ["district", "month"]
).any():
    raise ValueError("Duplicate baseline groups.")

if baseline_df[threshold_columns].isna().any().any():
    raise ValueError("Missing threshold values.")

# ============================================================
# 8. DISPLAY COVERAGE SUMMARY
# ============================================================

print("\n" + "=" * 65)
print("BASELINE COVERAGE SUMMARY")
print("=" * 65)

for variable in VARIABLES:

    coverage_col = f"{variable}_coverage_pct"

    print(f"\n{variable}")

    print(
        "Minimum coverage:",
        coverage_df[coverage_col].min(),
        "%"
    )

    print(
        "Maximum coverage:",
        coverage_df[coverage_col].max(),
        "%"
    )

print("\nFirst baseline rows:")
print(baseline_df.head(10).to_string(index=False))

# ============================================================
# 9. SAVE OUTPUTS
# ============================================================

baseline_df.to_csv(
    BASELINE_FILE,
    index=False
)

coverage_df.to_csv(
    COVERAGE_FILE,
    index=False
)

print("\n" + "=" * 65)
print("IFS BASELINE CONSTRUCTION COMPLETED")
print("=" * 65)

print("\nBaseline saved:")
print(BASELINE_FILE)

print("\nCoverage report saved:")
print(COVERAGE_FILE)

print("\nTotal baseline groups:", len(baseline_df))
print("Total threshold values:", len(baseline_df) * 6)

print("\nBaseline construction completed successfully.")
