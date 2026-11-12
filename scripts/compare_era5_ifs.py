
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================
# RISKWEAVE - ERA5 VS ECMWF IFS COMPARISON
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
    / "source_comparison_2024_2025"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

# Positive bias means IFS is higher than ERA5.
# Bias = IFS - ERA5

# ============================================================
# 1. LOAD DATASETS
# ============================================================

print("=" * 65)
print("ERA5 VS ECMWF IFS SOURCE COMPARISON")
print("=" * 65)

era5 = pd.read_csv(ERA5_FILE)
ifs = pd.read_csv(IFS_FILE)

era5["date"] = pd.to_datetime(
    era5["date"],
    errors="coerce"
).dt.normalize()

ifs["date"] = pd.to_datetime(
    ifs["date"],
    errors="coerce"
).dt.normalize()

# Select comparison period.
era5 = era5[
    era5["date"].between("2024-01-01", "2025-12-31")
].copy()

ifs = ifs[
    ifs["date"].between("2024-01-01", "2025-12-31")
].copy()

# ============================================================
# 2. CHECK REQUIRED COLUMNS
# ============================================================

required_columns = [
    "district",
    "date",
    *VARIABLES
]

for name, df in [
    ("ERA5", era5),
    ("IFS", ifs)
]:

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{name} missing columns: {missing}"
        )

    if df[required_columns].isna().any().any():
        raise ValueError(
            f"{name} contains missing comparison values."
        )

# ============================================================
# 3. CHECK DUPLICATE RECORDS
# ============================================================

for name, df in [
    ("ERA5", era5),
    ("IFS", ifs)
]:

    duplicates = df.duplicated(
        subset=["district", "date"]
    ).sum()

    print(f"{name} duplicate records: {duplicates}")

    if duplicates > 0:
        raise ValueError(
            f"{name} contains duplicate district-date records."
        )

# ============================================================
# 4. PREPARE COMPARISON COLUMNS
# ============================================================

era5_columns = [
    "district",
    "date",
    *VARIABLES
]

ifs_columns = [
    "district",
    "date",
    *VARIABLES
]

era5 = era5[era5_columns].copy()
ifs = ifs[ifs_columns].copy()

era5 = era5.rename(
    columns={
        variable: f"{variable}_era5"
        for variable in VARIABLES
    }
)

ifs = ifs.rename(
    columns={
        variable: f"{variable}_ifs"
        for variable in VARIABLES
    }
)

# ============================================================
# 5. MATCH DISTRICT-DATE RECORDS
# ============================================================

print("\nMatching ERA5 and IFS observations...")

comparison = pd.merge(
    era5,
    ifs,
    on=["district", "date"],
    how="outer",
    indicator=True,
    validate="one_to_one"
)

print("\nMatching results:")
print(comparison["_merge"].value_counts())

if not comparison["_merge"].eq("both").all():

    raise ValueError(
        "ERA5 and IFS records do not match completely."
    )

comparison = comparison.drop(
    columns=["_merge"]
)

expected_records = 25 * 731

if len(comparison) != expected_records:

    raise ValueError(
        f"Expected {expected_records} matched records, "
        f"found {len(comparison)}."
    )

# ============================================================
# 6. CALCULATE DAILY DIFFERENCES
# ============================================================

for variable in VARIABLES:

    comparison[f"{variable}_difference"] = (
        comparison[f"{variable}_ifs"]
        - comparison[f"{variable}_era5"]
    )

# ============================================================
# 7. CALCULATE OVERALL METRICS
# ============================================================

def calculate_metrics(group, variable):

    era5_values = group[
        f"{variable}_era5"
    ].to_numpy(dtype=float)

    ifs_values = group[
        f"{variable}_ifs"
    ].to_numpy(dtype=float)

    differences = ifs_values - era5_values

    correlation = np.corrcoef(
        era5_values,
        ifs_values
    )[0, 1]

    return {
        "variable": variable,
        "records": len(group),
        "era5_mean": np.mean(era5_values),
        "ifs_mean": np.mean(ifs_values),
        "mean_bias_ifs_minus_era5": np.mean(differences),
        "mae": np.mean(np.abs(differences)),
        "rmse": np.sqrt(np.mean(differences ** 2)),
        "correlation": correlation,
        "difference_std": np.std(differences, ddof=1)
    }


overall_results = pd.DataFrame([
    calculate_metrics(comparison, variable)
    for variable in VARIABLES
])

print("\n" + "=" * 65)
print("OVERALL COMPARISON RESULTS")
print("=" * 65)

print(
    overall_results.round(4).to_string(index=False)
)

# ============================================================
# 8. DISTRICT-LEVEL METRICS
# ============================================================

district_results = []

for district, group in comparison.groupby("district"):

    for variable in VARIABLES:

        result = calculate_metrics(
            group,
            variable
        )

        result["district"] = district

        district_results.append(result)

district_results = pd.DataFrame(district_results)

district_results = district_results[
    [
        "district",
        "variable",
        "records",
        "era5_mean",
        "ifs_mean",
        "mean_bias_ifs_minus_era5",
        "mae",
        "rmse",
        "correlation",
        "difference_std"
    ]
]

# ============================================================
# 9. SAVE RESULTS
# ============================================================

comparison_file = (
    OUTPUT_DIR / "matched_daily_comparison.csv"
)

overall_file = (
    OUTPUT_DIR / "overall_comparison_metrics.csv"
)

district_file = (
    OUTPUT_DIR / "district_comparison_metrics.csv"
)

comparison.to_csv(
    comparison_file,
    index=False
)

overall_results.to_csv(
    overall_file,
    index=False
)

district_results.to_csv(
    district_file,
    index=False
)

# ============================================================
# 10. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 65)
print("FINAL VALIDATION")
print("=" * 65)

print("Matched records:", len(comparison))
print("Districts:", comparison["district"].nunique())
print("Start date:", comparison["date"].min())
print("End date:", comparison["date"].max())

print("\nSaved files:")

print(comparison_file)
print(overall_file)
print(district_file)

print("\nComparison completed successfully.")
