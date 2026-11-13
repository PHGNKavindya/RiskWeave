
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_FILE = (
    PROJECT_ROOT
    / "data/raw/environmental_anomalies"
    / "ifs_baseline_2017_2023"
    / "ifs_baseline_2017_2023.csv"
)

COVERAGE_FILE = (
    PROJECT_ROOT
    / "data/raw/environmental_anomalies"
    / "ifs_baseline_2017_2023"
    / "ifs_baseline_2017_2023_coverage.csv"
)

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

print("=" * 60)
print("IFS BASELINE COLLECTION VALIDATION")
print("=" * 60)

df = pd.read_csv(DATA_FILE, parse_dates=["date"])
coverage = pd.read_csv(COVERAGE_FILE)

print("\nDataset shape:", df.shape)
print("Districts:", df["district"].nunique())
print("Start date:", df["date"].min())
print("End date:", df["date"].max())

print(
    "\nDuplicate district-date records:",
    df.duplicated(["district", "date"]).sum()
)

print("\nMissing values:")
print(df[VARIABLES].isna().sum())

print("\nCoverage report shape:", coverage.shape)

print("\nDistrict coverage:")
print(
    coverage[
        [
            "district",
            "precipitation_sum_coverage_pct",
            "temperature_2m_mean_coverage_pct",
            "relative_humidity_2m_mean_coverage_pct"
        ]
    ].to_string(index=False)
)

print("\nMonthly observation counts:")

df["month"] = df["date"].dt.month

monthly_counts = (
    df.groupby(["district", "month"])
    .agg(
        total_days=("date", "size"),
        valid_rainfall=("precipitation_sum", "count"),
        valid_temperature=("temperature_2m_mean", "count"),
        valid_humidity=("relative_humidity_2m_mean", "count")
    )
    .reset_index()
)

print(monthly_counts.head(15).to_string(index=False))

print("\nExpected monthly groups:", 25 * 12)
print("Actual monthly groups:", len(monthly_counts))

print("\nValidation inspection completed.")
