
from pathlib import Path
import requests
import pandas as pd

# ============================================================
# RISKWEAVE - ECMWF IFS API TEST
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

COORDINATES_FILE = (
    PROJECT_ROOT / "data" / "reference"
    / "district_coordinates.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "raw"
    / "environmental_anomalies"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2024-01-01"
END_DATE = "2025-12-31"

# ============================================================
# 1. LOAD AMPARA COORDINATES
# ============================================================

coordinates = pd.read_csv(COORDINATES_FILE)

district = coordinates.loc[
    coordinates["district"] == "Ampara"
].iloc[0]

latitude = float(district["latitude"])
longitude = float(district["longitude"])

print("=" * 65)
print("ECMWF IFS API TEST")
print("=" * 65)

print("District:", district["district"])
print("Latitude:", latitude)
print("Longitude:", longitude)

# ============================================================
# 2. PREPARE API PARAMETERS
# ============================================================

params = {
    "latitude": latitude,
    "longitude": longitude,
    "start_date": START_DATE,
    "end_date": END_DATE,
    "daily": (
        "precipitation_sum,"
        "temperature_2m_mean,"
        "relative_humidity_2m_mean"
    ),
    "timezone": "Asia/Colombo",
    "temperature_unit": "celsius",
    "precipitation_unit": "mm",
    "models": "ecmwf_ifs"
}

# ============================================================
# 3. SEND API REQUEST
# ============================================================

print("\nRequesting ECMWF IFS historical data...")

try:

    response = requests.get(
        API_URL,
        params=params,
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

except requests.exceptions.RequestException as error:

    raise RuntimeError(
        f"Open-Meteo API request failed: {error}"
    )

if data.get("error"):

    raise RuntimeError(
        f"Open-Meteo API error: {data.get('reason')}"
    )

# ============================================================
# 4. CHECK API RESPONSE
# ============================================================

if "daily" not in data:

    raise ValueError(
        "The API response does not contain daily weather data."
    )

daily_data = data["daily"]

required_columns = [
    "time",
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

missing_columns = [
    column
    for column in required_columns
    if column not in daily_data
]

if missing_columns:

    raise ValueError(
        f"API response is missing columns: {missing_columns}"
    )

# ============================================================
# 5. CREATE DATAFRAME
# ============================================================

df = pd.DataFrame(daily_data)

df = df.rename(
    columns={"time": "date"}
)

df["date"] = pd.to_datetime(
    df["date"],
    errors="coerce"
)

df["district"] = "Ampara"

df["data_source"] = "Open-Meteo ECMWF IFS"

# ============================================================
# 6. VALIDATE RESPONSE
# ============================================================

expected_dates = pd.date_range(
    START_DATE,
    END_DATE,
    freq="D"
)

print("\n" + "=" * 65)
print("API DATA VALIDATION")
print("=" * 65)

print("Records:", len(df))
print("Expected records:", len(expected_dates))

print("Start date:", df["date"].min())
print("End date:", df["date"].max())

print("Duplicate dates:", df["date"].duplicated().sum())

missing_dates = expected_dates.difference(
    pd.DatetimeIndex(df["date"])
)

print("Missing dates:", len(missing_dates))

print("\nMissing values:")
print(df[required_columns[1:]].isna().sum())

if len(df) != 731:
    raise ValueError("Expected exactly 731 daily records.")

if len(missing_dates) > 0:
    raise ValueError("Some expected dates are missing.")

if df["date"].duplicated().any():
    raise ValueError("Duplicate dates detected.")

if df[required_columns[1:]].isna().any().any():
    raise ValueError("Missing weather values detected.")

# ============================================================
# 7. SAVE TEST DATA
# ============================================================

output_file = (
    OUTPUT_DIR
    / "ifs_ampara_test_2024_2025.csv"
)

df.to_csv(
    output_file,
    index=False
)

print("\n" + "=" * 65)
print("API TEST COMPLETED")
print("=" * 65)

print("Returned grid latitude:", data.get("latitude"))
print("Returned grid longitude:", data.get("longitude"))
print("Returned elevation:", data.get("elevation"))

print("\nDaily units:")
print(data.get("daily_units"))

print("\nFirst five records:")
print(df.head().to_string(index=False))

print("\nSaved to:")
print(output_file)
