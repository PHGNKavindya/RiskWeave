
from pathlib import Path
import time
import requests
import pandas as pd

# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

COORDINATES_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "district_coordinates.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "environmental_anomalies"
    / "ifs_baseline_2017_2023_district_data"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "ampara_ifs_2017_2023.csv"


# ============================================================
# 2. API CONFIGURATION
# ============================================================

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2017-01-01"
END_DATE = "2023-12-31"

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

EXPECTED_DAYS = len(
    pd.date_range(START_DATE, END_DATE, freq="D")
)


# ============================================================
# 3. LOAD DISTRICT COORDINATES
# ============================================================

print("\n" + "=" * 65)
print("ECMWF IFS BASELINE API TEST")
print("=" * 65)

if not COORDINATES_FILE.exists():
    raise FileNotFoundError(
        f"Coordinates file not found: {COORDINATES_FILE}"
    )

coordinates = pd.read_csv(COORDINATES_FILE)

coordinates["district"] = (
    coordinates["district"].astype(str).str.strip()
)

district_row = coordinates.loc[
    coordinates["district"].str.lower() == "ampara"
]

if district_row.empty:
    raise ValueError(
        "Ampara was not found in district_coordinates.csv"
    )

latitude = float(district_row.iloc[0]["latitude"])
longitude = float(district_row.iloc[0]["longitude"])

print("\nDistrict: Ampara")
print(f"Latitude: {latitude}")
print(f"Longitude: {longitude}")

print(f"\nRequested period: {START_DATE} to {END_DATE}")
print(f"Expected daily records: {EXPECTED_DAYS}")


# ============================================================
# 4. PREPARE API REQUEST
# ============================================================

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


# ============================================================
# 5. COLLECT DATA WITH RETRIES
# ============================================================

print("\nRequesting ECMWF IFS historical data...")

data = None

for attempt in range(1, 4):

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=(15, 180)
        )

        response.raise_for_status()

        data = response.json()

        print("API request successful.")
        break

    except requests.RequestException as error:

        print(f"\nAttempt {attempt} failed.")
        print("Error:", error)

        if attempt == 3:
            raise

        wait_time = 10 * attempt

        print(f"Retrying in {wait_time} seconds...")
        time.sleep(wait_time)


# ============================================================
# 6. CHECK API RESPONSE
# ============================================================

if data is None:
    raise RuntimeError("No API response received.")

if "daily" not in data:
    raise ValueError(
        f"Daily weather data missing from API response: {data}"
    )

if "time" not in data["daily"]:
    raise ValueError(
        "Date information is missing from the API response."
    )


# ============================================================
# 7. CREATE DATAFRAME
# ============================================================

daily = pd.DataFrame(data["daily"])

# Rename the API time column only once.
daily = daily.rename(
    columns={"time": "date"}
)

# Convert date column to datetime.
daily["date"] = pd.to_datetime(
    daily["date"],
    errors="coerce"
)

# Add district name.
daily["district"] = "Ampara"

# Check that requested variables exist.
missing_columns = [
    column
    for column in VARIABLES
    if column not in daily.columns
]

if missing_columns:
    raise ValueError(
        f"Missing weather columns: {missing_columns}"
    )

# Convert weather variables to numeric.
for column in VARIABLES:

    daily[column] = pd.to_numeric(
        daily[column],
        errors="coerce"
    )

# Keep only required columns.
daily = daily[
    ["district", "date"] + VARIABLES
].copy()

daily = daily.sort_values("date").reset_index(drop=True)


# ============================================================
# 8. BASIC DATA VALIDATION
# ============================================================

print("\n" + "=" * 65)
print("BASIC DATA VALIDATION")
print("=" * 65)

print("\nDataset shape:", daily.shape)

print("\nFirst five records:")
print(daily.head().to_string(index=False))

print("\nLast five records:")
print(daily.tail().to_string(index=False))

print("\nExpected records:", EXPECTED_DAYS)
print("Actual records:", len(daily))

print("\nDate coverage:")
print("Start:", daily["date"].min())
print("End:", daily["date"].max())

print(
    "\nDuplicate dates:",
    daily["date"].duplicated().sum()
)


# ============================================================
# 9. MISSING VALUE ANALYSIS
# ============================================================

print("\n" + "=" * 65)
print("MISSING VALUE ANALYSIS")
print("=" * 65)

print("\nMissing values by variable:")

missing_counts = daily[VARIABLES].isna().sum()

print(missing_counts)

total_missing = int(
    missing_counts.sum()
)

print("\nTotal missing weather values:", total_missing)

# Identify rows containing missing values.
missing_rows = daily.loc[
    daily[VARIABLES].isna().any(axis=1)
]

print("\nRows containing missing weather values:")

if missing_rows.empty:

    print("No missing weather observations.")

else:

    print(
        missing_rows.to_string(index=False)
    )

    print("\nDates containing missing values:")

    print(
        missing_rows["date"].tolist()
    )


# ============================================================
# 10. DATE CONTINUITY VALIDATION
# ============================================================

print("\n" + "=" * 65)
print("DATE CONTINUITY VALIDATION")
print("=" * 65)

expected_dates = pd.date_range(
    start=START_DATE,
    end=END_DATE,
    freq="D"
)

actual_dates = pd.DatetimeIndex(
    daily["date"].dropna().unique()
)

missing_dates = expected_dates.difference(
    actual_dates
)

unexpected_dates = actual_dates.difference(
    expected_dates
)

print("Expected dates:", len(expected_dates))
print("Actual unique dates:", len(actual_dates))

print("Missing dates:", len(missing_dates))
print("Unexpected dates:", len(unexpected_dates))

if len(missing_dates) > 0:

    print("\nMissing dates:")

    print(missing_dates.tolist())

if len(unexpected_dates) > 0:

    print("\nUnexpected dates:")

    print(unexpected_dates.tolist())


# ============================================================
# 11. WEATHER VARIABLE RANGE CHECKS
# ============================================================

print("\n" + "=" * 65)
print("WEATHER VARIABLE RANGE ANALYSIS")
print("=" * 65)

print("\nDescriptive statistics:")

print(
    daily[VARIABLES].describe()
)

# Negative rainfall check.
negative_rainfall = (
    daily["precipitation_sum"] < 0
).sum()

# Relative humidity range check.
invalid_humidity = (
    (daily["relative_humidity_2m_mean"] < 0)
    |
    (daily["relative_humidity_2m_mean"] > 100)
).sum()

print("\nNegative rainfall observations:", negative_rainfall)

print(
    "Humidity observations outside 0-100:",
    invalid_humidity
)


# ============================================================
# 12. FINAL VALIDATION
# ============================================================

print("\n" + "=" * 65)
print("FINAL VALIDATION")
print("=" * 65)

checks = {
    "Expected record count": len(daily) == EXPECTED_DAYS,

    "No duplicate dates": (
        daily["date"].duplicated().sum() == 0
    ),

    "No missing dates": len(missing_dates) == 0,

    "No unexpected dates": len(unexpected_dates) == 0,

    "No missing weather values": (
        daily[VARIABLES].notna().all().all()
    ),

    "No negative rainfall": negative_rainfall == 0,

    "Valid humidity range": invalid_humidity == 0,

    "No invalid dates": daily["date"].notna().all()
}

for check_name, passed in checks.items():

    status = "PASS" if passed else "FAIL"

    print(f"{check_name}: {status}")

all_valid = all(checks.values())


# ============================================================
# 13. SAVE VALIDATED DATA
# ============================================================

print("\n" + "=" * 65)
print("SAVE RESULTS")
print("=" * 65)

if all_valid:

    daily.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nSUCCESS: All validation checks passed.")

    print("Saved file:")
    print(OUTPUT_FILE)

else:

    print("\nVALIDATION FAILED.")

    print(
        "The dataset has not been saved as a validated baseline file."
    )


# ============================================================
# 14. API METADATA
# ============================================================

print("\n" + "=" * 65)
print("API METADATA")
print("=" * 65)

print("Requested model: ecmwf_ifs")

print(
    "Daily units:",
    data.get("daily_units", {})
)

print(
    "Grid latitude:",
    data.get("latitude")
)

print(
    "Grid longitude:",
    data.get("longitude")
)

print(
    "Grid elevation:",
    data.get("elevation")
)

print("\nAPI test completed.")
