
from pathlib import Path
import pandas as pd
import numpy as np

# ============================================================
# RISKWEAVE - DISTRICT AND MONTHLY SOURCE DIFFERENCES
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "environmental_anomalies"
    / "source_comparison_2024_2025"
)

DISTRICT_FILE = DATA_DIR / "district_comparison_metrics.csv"
MATCHED_FILE = DATA_DIR / "matched_daily_comparison.csv"

OUTPUT_DIR = DATA_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

# ============================================================
# 1. LOAD DATA
# ============================================================

district_df = pd.read_csv(DISTRICT_FILE)
matched_df = pd.read_csv(MATCHED_FILE)

matched_df["date"] = pd.to_datetime(
    matched_df["date"],
    errors="coerce"
)

matched_df["month"] = matched_df["date"].dt.month

# ============================================================
# 2. DISTRICT-LEVEL SUMMARY
# ============================================================

print("=" * 65)
print("DISTRICT-LEVEL SOURCE DIFFERENCES")
print("=" * 65)

for variable in VARIABLES:

    subset = district_df[
        district_df["variable"] == variable
    ].copy()

    print(f"\nVARIABLE: {variable}")

    print("\nHighest positive biases:")

    print(
        subset.nlargest(
            5,
            "mean_bias_ifs_minus_era5"
        )[
            [
                "district",
                "mean_bias_ifs_minus_era5",
                "mae",
                "correlation"
            ]
        ].round(3).to_string(index=False)
    )

    print("\nHighest negative biases:")

    print(
        subset.nsmallest(
            5,
            "mean_bias_ifs_minus_era5"
        )[
            [
                "district",
                "mean_bias_ifs_minus_era5",
                "mae",
                "correlation"
            ]
        ].round(3).to_string(index=False)
    )

    print("\nDistrict-level metric ranges:")

    print(
        subset[
            [
                "mean_bias_ifs_minus_era5",
                "mae",
                "rmse",
                "correlation"
            ]
        ].agg(["min", "median", "max"]).round(3)
    )

# ============================================================
# 3. MONTHLY SOURCE DIFFERENCES
# ============================================================

print("\n" + "=" * 65)
print("MONTHLY SOURCE DIFFERENCES")
print("=" * 65)

monthly_results = []

for variable in VARIABLES:

    era5_col = f"{variable}_era5"
    ifs_col = f"{variable}_ifs"

    for month, group in matched_df.groupby("month"):

        era5_values = group[era5_col].to_numpy(dtype=float)
        ifs_values = group[ifs_col].to_numpy(dtype=float)

        differences = ifs_values - era5_values

        monthly_results.append({
            "variable": variable,
            "month": int(month),
            "records": len(group),
            "era5_mean": np.mean(era5_values),
            "ifs_mean": np.mean(ifs_values),
            "mean_bias_ifs_minus_era5": np.mean(differences),
            "mae": np.mean(np.abs(differences)),
            "rmse": np.sqrt(np.mean(differences ** 2))
        })

monthly_df = pd.DataFrame(monthly_results)

print(
    monthly_df.round(3).to_string(index=False)
)

# ============================================================
# 4. SAVE RESULTS
# ============================================================

district_output = (
    OUTPUT_DIR / "district_source_difference_analysis.csv"
)

monthly_output = (
    OUTPUT_DIR / "monthly_source_difference_analysis.csv"
)

district_df.to_csv(
    district_output,
    index=False
)

monthly_df.to_csv(
    monthly_output,
    index=False
)

print("\n" + "=" * 65)
print("ANALYSIS COMPLETED")
print("=" * 65)

print("Saved:")
print(district_output)
print(monthly_output)
