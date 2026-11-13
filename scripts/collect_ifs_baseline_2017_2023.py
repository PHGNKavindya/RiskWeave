
from pathlib import Path
import re
import time
import requests
import pandas as pd

# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

COORDINATES_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "district_coordinates.csv"
)

BASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "environmental_anomalies"
)

CHECKPOINT_DIR = (
    BASE_DIR
    / "ifs_baseline_2017_2023_district_data"
)

OUTPUT_DIR = (
    BASE_DIR
    / "ifs_baseline_2017_2023"
)

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FINAL_DATA_FILE = (
    OUTPUT_DIR
    / "ifs_baseline_2017_2023.csv"
)

COVERAGE_FILE = (
    OUTPUT_DIR
    / "ifs_baseline_2017_2023_coverage.csv"
)

# ============================================================
# 2. API CONFIGURATION
# ============================================================

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2017-01-01"
END_DATE = "2023-12-31"

EXPECTED_DATES = pd.date_range(
    START_DATE,
    END_DATE,
    freq="D"
)

EXPECTED_DAYS = len(EXPECTED_DATES)

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

EXPECTED_DISTRICTS = 25

MAX_ATTEMPTS = 3

# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def safe_filename(district):
    """Convert district name into a safe filename."""

    filename = re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        str(district).strip().lower()
    )

    return filename.strip("_")


def validate_district_data(df, district):
    """
    Validate district data.

    Missing weather values are allowed and preserved.
    Missing dates and duplicate dates are not allowed.
    """

    required_columns = [
        "district",
        "date"
    ] + VARIABLES

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{district}: Missing columns: {missing_columns}"
        )

    df = df[required_columns].copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    for column in VARIABLES:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    if df["date"].isna().any():
        raise ValueError(
            f"{district}: Invalid dates found."
        )

    df = df.sort_values("date").reset_index(drop=True)

    if df["date"].duplicated().any():
        raise ValueError(
            f"{district}: Duplicate dates found."
        )

    actual_dates = pd.DatetimeIndex(df["date"])

    missing_dates = EXPECTED_DATES.difference(actual_dates)
    unexpected_dates = actual_dates.difference(EXPECTED_DATES)

    if len(df) != EXPECTED_DAYS:
        raise ValueError(
            f"{district}: Expected {EXPECTED_DAYS} records, "
            f"received {len(df)}."
        )

    if len(missing_dates) > 0:
        raise ValueError(
            f"{district}: {len(missing_dates)} missing dates."
        )

    if len(unexpected_dates) > 0:
        raise ValueError(
            f"{district}: Unexpected dates found."
        )

    if not (df["district"] == district).all():
        raise ValueError(
            f"{district}: District name mismatch."
        )

    # Missing weather values are intentionally not rejected.
    return df


def collect_district(district, latitude, longitude):
    """Collect ECMWF IFS historical data for one district."""

    filename = (
        safe_filename(district)
        + "_ifs_2017_2023.csv"
    )

    output_file = CHECKPOINT_DIR / filename

    # --------------------------------------------------------
    # Reuse an existing valid checkpoint
    # --------------------------------------------------------

    if output_file.exists():

        try:
            existing_df = pd.read_csv(output_file)

            existing_df = validate_district_data(
                existing_df,
                district
            )

            print(
                f"\nCHECKPOINT REUSED: {district}"
            )

            return existing_df

        except Exception as error:

            print(
                f"\nExisting checkpoint invalid for {district}: "
                f"{error}"
            )

            print("Recollecting district data...")

    # --------------------------------------------------------
    # API request
    # --------------------------------------------------------

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(VARIABLES),
        "timezone": "Asia/Colombo",
        "models": "ecmwf_ifs",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius"
    }

    response_data = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        try:

            print(
                f"\nRequesting {district} "
                f"(attempt {attempt}/{MAX_ATTEMPTS})"
            )

            response = requests.get(
                API_URL,
                params=params,
                timeout=(15, 180)
            )

            response.raise_for_status()

            response_data = response.json()

            break

        except requests.RequestException as error:

            print(
                f"API request failed for {district}: {error}"
            )

            if attempt == MAX_ATTEMPTS:
                raise

            wait_time = 10 * attempt

            print(
                f"Waiting {wait_time} seconds before retry..."
            )

            time.sleep(wait_time)

    if response_data is None:
        raise RuntimeError(
            f"No API response for {district}."
        )

    if "daily" not in response_data:
        raise ValueError(
            f"Daily data missing for {district}."
        )

    daily = pd.DataFrame(response_data["daily"])

    if "time" not in daily.columns:
        raise ValueError(
            f"Date column missing for {district}."
        )

    daily = daily.rename(
        columns={"time": "date"}
    )

    daily["district"] = district

    daily = validate_district_data(
        daily,
        district
    )

    # --------------------------------------------------------
    # Save district checkpoint
    # --------------------------------------------------------

    daily.to_csv(
        output_file,
        index=False
    )

    missing_values = int(
        daily[VARIABLES].isna().sum().sum()
    )

    print(
        f"SUCCESS: {district} | "
        f"Records: {len(daily)} | "
        f"Missing weather values: {missing_values}"
    )

    return daily


# ============================================================
# 4. LOAD DISTRICT COORDINATES
# ============================================================

print("\n" + "=" * 70)
print("ECMWF IFS BASELINE COLLECTION")
print("=" * 70)

if not COORDINATES_FILE.exists():
    raise FileNotFoundError(
        f"Coordinates file not found: {COORDINATES_FILE}"
    )

coordinates = pd.read_csv(COORDINATES_FILE)

required_coordinate_columns = [
    "district",
    "latitude",
    "longitude"
]

for column in required_coordinate_columns:
    if column not in coordinates.columns:
        raise ValueError(
            f"Coordinates file missing column: {column}"
        )

coordinates = coordinates[
    required_coordinate_columns
].copy()

coordinates["district"] = (
    coordinates["district"].astype(str).str.strip()
)

coordinates["latitude"] = pd.to_numeric(
    coordinates["latitude"],
    errors="coerce"
)

coordinates["longitude"] = pd.to_numeric(
    coordinates["longitude"],
    errors="coerce"
)

if coordinates.isna().any().any():
    raise ValueError(
        "Missing or invalid district coordinates found."
    )

if coordinates["district"].duplicated().any():
    raise ValueError(
        "Duplicate district names found in coordinates."
    )

if len(coordinates) != EXPECTED_DISTRICTS:
    raise ValueError(
        f"Expected {EXPECTED_DISTRICTS} districts, "
        f"found {len(coordinates)}."
    )

print("\nDistricts found:", len(coordinates))
print("Expected days per district:", EXPECTED_DAYS)
print(
    "Expected total records:",
    len(coordinates) * EXPECTED_DAYS
)


# ============================================================
# 5. COLLECT ALL DISTRICTS
# ============================================================

district_datasets = []

failed_districts = []

for index, row in coordinates.iterrows():

    district = row["district"]

    latitude = float(row["latitude"])
    longitude = float(row["longitude"])

    print("\n" + "-" * 70)

    print(
        f"DISTRICT {index + 1}/{EXPECTED_DISTRICTS}: "
        f"{district}"
    )

    try:

        district_df = collect_district(
            district,
            latitude,
            longitude
        )

        district_datasets.append(district_df)

    except Exception as error:

        print(
            f"\nFAILED: {district}"
        )

        print("Reason:", error)

        failed_districts.append(
            {
                "district": district,
                "error": str(error)
            }
        )

    # Small pause between district requests.
    time.sleep(2)


# ============================================================
# 6. STOP IF ANY DISTRICTS FAILED
# ============================================================

if failed_districts:

    print("\n" + "=" * 70)
    print("COLLECTION INCOMPLETE")
    print("=" * 70)

    print(
        "Successful districts:",
        len(district_datasets)
    )

    print(
        "Failed districts:",
        len(failed_districts)
    )

    for item in failed_districts:
        print(
            item["district"],
            "->",
            item["error"]
        )

    print("\nCompleted district checkpoints are preserved.")
    print("Run the script again after resolving failures.")

    raise SystemExit(
        "Collection incomplete. Combined dataset not created."
    )


# ============================================================
# 7. COMBINE DISTRICT DATASETS
# ============================================================

print("\n" + "=" * 70)
print("COMBINING DISTRICT DATA")
print("=" * 70)

combined_df = pd.concat(
    district_datasets,
    ignore_index=True
)

combined_df = combined_df.sort_values(
    ["district", "date"]
).reset_index(drop=True)

print("Combined shape:", combined_df.shape)

print(
    "District count:",
    combined_df["district"].nunique()
)

print(
    "Date coverage:",
    combined_df["date"].min(),
    "to",
    combined_df["date"].max()
)


# ============================================================
# 8. COMBINED DATA VALIDATION
# ============================================================

print("\n" + "=" * 70)
print("COMBINED DATA VALIDATION")
print("=" * 70)

duplicate_count = combined_df.duplicated(
    subset=["district", "date"]
).sum()

expected_total_records = (
    EXPECTED_DISTRICTS * EXPECTED_DAYS
)

print("Expected total records:", expected_total_records)
print("Actual total records:", len(combined_df))
print("Duplicate district-date records:", duplicate_count)

district_record_counts = (
    combined_df.groupby("district")
    .size()
)

print("\nRecords per district:")
print(district_record_counts.to_string())

if len(combined_df) != expected_total_records:
    raise ValueError(
        "Combined record count validation failed."
    )

if combined_df["district"].nunique() != EXPECTED_DISTRICTS:
    raise ValueError(
        "Combined district count validation failed."
    )

if duplicate_count != 0:
    raise ValueError(
        "Duplicate district-date records found."
    )

if not (district_record_counts == EXPECTED_DAYS).all():
    raise ValueError(
        "District record count validation failed."
    )


# ============================================================
# 9. MISSING VALUE COVERAGE REPORT
# ============================================================

print("\n" + "=" * 70)
print("MISSING VALUE COVERAGE REPORT")
print("=" * 70)

coverage_rows = []

for district, group in combined_df.groupby("district"):

    row = {
        "district": district,
        "total_days": len(group)
    }

    for variable in VARIABLES:

        missing_count = int(
            group[variable].isna().sum()
        )

        valid_count = int(
            group[variable].notna().sum()
        )

        coverage_percentage = (
            valid_count / len(group) * 100
        )

        row[f"{variable}_valid_days"] = valid_count

        row[f"{variable}_missing_days"] = missing_count

        row[f"{variable}_coverage_pct"] = round(
            coverage_percentage,
            2
        )

    row["days_with_any_missing_variable"] = int(
        group[VARIABLES].isna().any(axis=1).sum()
    )

    coverage_rows.append(row)


coverage_df = pd.DataFrame(coverage_rows)

print(
    coverage_df.to_string(index=False)
)

total_missing_values = int(
    combined_df[VARIABLES].isna().sum().sum()
)

print(
    "\nTotal missing weather values:",
    total_missing_values
)


# ============================================================
# 10. SAVE FINAL DATASETS
# ============================================================

print("\n" + "=" * 70)
print("SAVING FINAL DATASETS")
print("=" * 70)

combined_df.to_csv(
    FINAL_DATA_FILE,
    index=False
)

coverage_df.to_csv(
    COVERAGE_FILE,
    index=False
)

print("\nCombined IFS dataset saved:")
print(FINAL_DATA_FILE)

print("\nCoverage report saved:")
print(COVERAGE_FILE)


# ============================================================
# 11. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("COLLECTION COMPLETED SUCCESSFULLY")
print("=" * 70)

print("Model: ECMWF IFS")

print("Period:", START_DATE, "to", END_DATE)

print("Districts:", combined_df["district"].nunique())

print("Days per district:", EXPECTED_DAYS)

print("Total records:", len(combined_df))

print("Missing weather values:", total_missing_values)

print("Duplicate records:", duplicate_count)

print("\nOutput files:")
print("1.", FINAL_DATA_FILE)
print("2.", COVERAGE_FILE)

print("\nDistrict checkpoints:")
print(CHECKPOINT_DIR)

print("\nECMWF IFS baseline collection completed.")
