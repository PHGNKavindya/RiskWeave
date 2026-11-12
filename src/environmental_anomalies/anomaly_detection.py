from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path.cwd()

ERA5_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_era5_combined_2006_2026.csv"
)

COORDINATES_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "district_coordinates.csv"
)

# --------------------------------------------------
# 1. Inspect ERA5 dataset
# --------------------------------------------------

print("=" * 65)
print("ERA5 DATASET INSPECTION")
print("=" * 65)

era5 = pd.read_csv(ERA5_FILE)

era5["date"] = pd.to_datetime(
    era5["date"],
    errors="coerce"
)

print("Shape:", era5.shape)
print("\nColumns:")
print(era5.columns.tolist())

print("\nDate coverage:")
print(era5["date"].min(), "to", era5["date"].max())

comparison_era5 = era5[
    (era5["date"] >= "2024-01-01")
    & (era5["date"] <= "2025-12-31")
].copy()

print("\n2024–2025 ERA5 records:", len(comparison_era5))
print("Districts:", comparison_era5["district"].nunique())

print("\nRecords per district:")
print(comparison_era5.groupby("district").size())

# --------------------------------------------------
# 2. Inspect district coordinates
# --------------------------------------------------

print("\n" + "=" * 65)
print("DISTRICT COORDINATES INSPECTION")
print("=" * 65)

coordinates = pd.read_csv(COORDINATES_FILE)

print("Shape:", coordinates.shape)

print("\nColumns:")
print(coordinates.columns.tolist())

print("\nFirst five records:")
print(coordinates.head().to_string(index=False))

print("\nMissing values:")
print(coordinates.isna().sum())

print("\nInspection completed.")