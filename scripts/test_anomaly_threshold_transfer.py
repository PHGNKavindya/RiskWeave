
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================
# RISKWEAVE - ERA5 ANOMALY THRESHOLD TRANSFER TEST
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ERA5_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_era5_combined_2006_2026.csv"
)

IFS_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "environmental_anomalies"
    / "ifs_comparison_2024_2025.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "environmental_anomalies"
    / "threshold_transfer_2024_2025"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VARIABLES = {
    "precipitation_sum": "rainfall",
    "temperature_2m_mean": "temperature",
    "relative_humidity_2m_mean": "humidity"
}

BASELINE_START = "2007-01-01"
BASELINE_END = "2023-12-31"

TEST_START = "2024-01-01"
TEST_END = "2025-12-31"

# ============================================================
# 1. LOAD DATA
# ============================================================

print("=" * 65)
print("ANOMALY THRESHOLD TRANSFER VALIDATION")
print("=" * 65)

era5 = pd.read_csv(ERA5_FILE)
ifs = pd.read_csv(IFS_FILE)

for df in (era5, ifs):

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    ).dt.normalize()

    df["district"] = df["district"].astype(str).str.strip()

    df["month"] = df["date"].dt.month

# ============================================================
# 2. CREATE HISTORICAL BASELINE
# ============================================================

baseline = era5[
    era5["date"].between(
        BASELINE_START,
        BASELINE_END
    )
].copy()

if baseline.empty:
    raise ValueError("Historical baseline data is empty.")

threshold_records = []

for (district, month), group in baseline.groupby(
    ["district", "month"]
):

    record = {
        "district": district,
        "month": month
    }

    for variable in VARIABLES:

        record[f"{variable}_q01"] = group[
            variable
        ].quantile(0.01)

        record[f"{variable}_q99"] = group[
            variable
        ].quantile(0.99)

    threshold_records.append(record)

thresholds = pd.DataFrame(threshold_records)

if len(thresholds) != 25 * 12:
    raise ValueError(
        "Expected 300 district-month baseline groups."
    )

print("\nBaseline records:", len(baseline))
print("Threshold groups:", len(thresholds))

# ============================================================
# 3. PREPARE HELD-OUT COMPARISON DATA
# ============================================================

era5_test = era5[
    era5["date"].between(TEST_START, TEST_END)
].copy()

ifs_test = ifs[
    ifs["date"].between(TEST_START, TEST_END)
].copy()

comparison = pd.merge(
    era5_test[
        ["district", "date", "month", *VARIABLES]
    ],
    ifs_test[
        ["district", "date", *VARIABLES]
    ],
    on=["district", "date"],
    how="inner",
    suffixes=("_era5", "_ifs"),
    validate="one_to_one"
)

if len(comparison) != 18275:
    raise ValueError(
        f"Expected 18,275 matched records, got {len(comparison)}."
    )

comparison = comparison.merge(
    thresholds,
    on=["district", "month"],
    how="left",
    validate="many_to_one"
)

if comparison.isna().any().any():
    raise ValueError(
        "Missing values found after threshold matching."
    )

# ============================================================
# 4. APPLY IDENTICAL ERA5 THRESHOLDS
# ============================================================

flag_results = []

for variable, label in VARIABLES.items():

    lower = f"{variable}_q01"
    upper = f"{variable}_q99"

    era5_values = comparison[
        f"{variable}_era5"
    ]

    ifs_values = comparison[
        f"{variable}_ifs"
    ]

    comparison[f"{label}_era5_anomaly"] = (
        (era5_values < comparison[lower])
        | (era5_values > comparison[upper])
    )

    comparison[f"{label}_ifs_anomaly"] = (
        (ifs_values < comparison[lower])
        | (ifs_values > comparison[upper])
    )

    era5_flag = comparison[
        f"{label}_era5_anomaly"
    ].astype(bool)

    ifs_flag = comparison[
        f"{label}_ifs_anomaly"
    ].astype(bool)

    tp = int((era5_flag & ifs_flag).sum())
    tn = int((~era5_flag & ~ifs_flag).sum())
    fp = int((~era5_flag & ifs_flag).sum())
    fn = int((era5_flag & ~ifs_flag).sum())

    total = len(comparison)

    agreement = (tp + tn) / total

    positive_agreement = (
        tp / (tp + fn)
        if (tp + fn) > 0 else np.nan
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0 else np.nan
    )

    flag_results.append({
        "variable": variable,
        "era5_anomaly_days": int(era5_flag.sum()),
        "ifs_anomaly_days": int(ifs_flag.sum()),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "overall_agreement": agreement,
        "positive_agreement": positive_agreement,
        "precision": precision
    })

# ============================================================
# 5. SAVE RESULTS
# ============================================================

flag_summary = pd.DataFrame(flag_results)

thresholds.to_csv(
    OUTPUT_DIR / "experimental_era5_thresholds_2007_2023.csv",
    index=False
)

comparison.to_csv(
    OUTPUT_DIR / "threshold_transfer_daily_results.csv",
    index=False
)

flag_summary.to_csv(
    OUTPUT_DIR / "threshold_transfer_summary.csv",
    index=False
)

# ============================================================
# 6. DISPLAY RESULTS
# ============================================================

print("\n" + "=" * 65)
print("THRESHOLD TRANSFER RESULTS")
print("=" * 65)

print(
    flag_summary.round(4).to_string(index=False)
)

print("\n" + "=" * 65)
print("VALIDATION SUMMARY")
print("=" * 65)

print("Matched observations:", len(comparison))
print("Districts:", comparison["district"].nunique())
print("Baseline period:", BASELINE_START, "to", BASELINE_END)
print("Test period:", TEST_START, "to", TEST_END)

print("\nSaved results to:")
print(OUTPUT_DIR)

print("\nThreshold transfer experiment completed.")
