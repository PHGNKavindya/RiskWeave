
from pathlib import Path
import pandas as pd


# ==================================================
# RISKWEAVE OPERATIONAL DATA VERIFICATION
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parent

FILES = {
    "ERA5": (
        PROJECT_ROOT
        / "data"
        / "processed"
        / "weather_era5_combined_2006_2026.csv"
    ),

    "Historical API": (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "weather_live"
        / "recent_historical_weather.csv"
    ),

    "Forecast API": (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "weather_live"
        / "yesterday_completed_weather.csv"
    )
}


# ==================================================
# 1. LOAD AND VERIFY INDIVIDUAL DATASETS
# ==================================================

datasets = []

print("=" * 65)
print("RISKWEAVE OPERATIONAL DATA VERIFICATION")
print("=" * 65)

for source_name, file_path in FILES.items():

    print(f"\nChecking: {source_name}")

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )

    df = pd.read_csv(file_path)

    required_columns = [
        "district",
        "date"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{source_name} missing columns: "
            f"{missing_columns}"
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["district"] = (
        df["district"]
        .astype(str)
        .str.strip()
    )

    if df["date"].isna().any():
        raise ValueError(
            f"{source_name} contains invalid dates."
        )

    print("Rows:", len(df))
    print("Districts:", df["district"].nunique())
    print("Start date:", df["date"].min().date())
    print("End date:", df["date"].max().date())

    if "data_source" not in df.columns:
        df["data_source"] = source_name

    datasets.append(df)


# ==================================================
# 2. COMBINE DATASETS IN MEMORY
# ==================================================

combined = pd.concat(
    datasets,
    ignore_index=True
)

combined["date"] = pd.to_datetime(
    combined["date"]
).dt.normalize()

combined = combined.sort_values(
    ["district", "date"]
).reset_index(drop=True)


# ==================================================
# 3. CHECK OVERALL COVERAGE
# ==================================================

print("\n" + "=" * 65)
print("COMBINED DATASET SUMMARY")
print("=" * 65)

print("Total rows:", len(combined))

print(
    "Unique districts:",
    combined["district"].nunique()
)

print(
    "Start date:",
    combined["date"].min().date()
)

print(
    "End date:",
    combined["date"].max().date()
)


# ==================================================
# 4. CHECK DUPLICATE DISTRICT-DATE RECORDS
# ==================================================

duplicates = combined[
    combined.duplicated(
        subset=["district", "date"],
        keep=False
    )
]

print("\nDuplicate district-date records:", len(duplicates))

if not duplicates.empty:

    print("\nDuplicate examples:")

    print(
        duplicates[
            ["district", "date", "data_source"]
        ].head(20).to_string(index=False)
    )


# ==================================================
# 5. CHECK RECORDS PER DISTRICT
# ==================================================

print("\nRecords per district:")

print(
    combined.groupby("district")
    .size()
    .to_string()
)


# ==================================================
# 6. CHECK DATA SOURCE COUNTS
# ==================================================

print("\nData source counts:")

print(
    combined["data_source"]
    .value_counts(dropna=False)
    .to_string()
)


# ==================================================
# 7. CHECK DAILY DATE CONTINUITY PER DISTRICT
# ==================================================

print("\n" + "=" * 65)
print("DISTRICT DATE CONTINUITY")
print("=" * 65)

for district, group in combined.groupby("district"):

    dates = pd.DatetimeIndex(
        group["date"].drop_duplicates().sort_values()
    )

    expected_dates = pd.date_range(
        dates.min(),
        dates.max(),
        freq="D"
    )

    missing_dates = expected_dates.difference(
        dates
    )

    print(
        district,
        "| Missing dates:",
        len(missing_dates)
    )

    if len(missing_dates) > 0:
        print(
            "Missing examples:",
            missing_dates[:10].strftime("%Y-%m-%d").tolist()
        )


# ==================================================
# 8. FINAL DUPLICATE STATUS
# ==================================================

print("\n" + "=" * 65)
print("VERIFICATION COMPLETED")
print("=" * 65)

if duplicates.empty:
    print("No duplicate district-date records found.")
else:
    print("Duplicate records require investigation.")

print(
    "\nOriginal ERA5 dataset was not modified."
)

print(
    "No operational combined CSV has been created yet."
)
