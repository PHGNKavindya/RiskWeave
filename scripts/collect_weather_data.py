
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests


# ==========================================================
# 1. PROJECT PATHS
# ==========================================================

PROJECT_DIR = Path(__file__).resolve().parents[1]

COORDINATES_FILE = (
    PROJECT_DIR / "data" / "reference" /
    "district_coordinates.csv"
)

RAW_DIR = PROJECT_DIR / "data" / "raw"
JSON_DIR = RAW_DIR / "open_meteo_json"

RAW_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# 2. API CONFIGURATION
# ==========================================================

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2024-12-30"

# ERA5 historical data has approximately a 5-day delay.
today = datetime.now(ZoneInfo("Asia/Colombo")).date()
END_DATE = (today - timedelta(days=5)).isoformat()

TIMEZONE = "Asia/Colombo"

DAILY_VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min"
]

MODEL = "era5"


# ==========================================================
# 3. LOAD DISTRICT COORDINATES
# ==========================================================

print("Loading district coordinates...")

if not COORDINATES_FILE.exists():
    raise FileNotFoundError(
        f"Coordinate file not found: {COORDINATES_FILE}"
    )

coordinates = pd.read_csv(COORDINATES_FILE)

required_columns = {
    "district",
    "latitude",
    "longitude"
}

if not required_columns.issubset(coordinates.columns):
    raise ValueError(
        "Coordinate CSV must contain: district, latitude, longitude"
    )

if coordinates["district"].duplicated().any():
    raise ValueError("Duplicate district names found.")

if coordinates[list(required_columns)].isna().any().any():
    raise ValueError("Missing district names or coordinates found.")

if len(coordinates) != 25:
    raise ValueError(
        f"Expected 25 districts, found {len(coordinates)}."
    )

print(f"Loaded {len(coordinates)} districts.")


# ==========================================================
# 4. FUNCTION TO COLLECT WEATHER FOR ONE DISTRICT
# ==========================================================

def collect_district_weather(row):

    district = row["district"]
    latitude = float(row["latitude"])
    longitude = float(row["longitude"])

    print(f"\nCollecting weather for {district}...")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "models": MODEL
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    if result.get("error"):
        raise ValueError(result.get("reason", "API returned an error."))

    if "daily" not in result:
        raise ValueError("Daily weather data was not returned.")

    daily_data = result["daily"]

    # Check that all requested variables were returned.
    missing_variables = [
        variable
        for variable in DAILY_VARIABLES
        if variable not in daily_data
    ]

    if missing_variables:
        raise ValueError(
            f"Missing API variables: {missing_variables}"
        )

    # Convert API response into a DataFrame.
    weather = pd.DataFrame(daily_data)

    # Add district and coordinate information.
    weather["district"] = district

    weather["representative_latitude"] = latitude
    weather["representative_longitude"] = longitude

    # Keep the actual coordinates of the API grid location.
    weather["api_grid_latitude"] = result.get("latitude")
    weather["api_grid_longitude"] = result.get("longitude")
    weather["api_grid_elevation_m"] = result.get("elevation")

    weather["weather_model"] = MODEL
    weather["weather_source"] = "Open-Meteo Historical Weather API"
    weather["timezone"] = TIMEZONE

    # Rename the date column.
    weather = weather.rename(columns={"time": "date"})

    # Convert date strings to dates.
    weather["date"] = pd.to_datetime(weather["date"])

    # Save the original API response for traceability.
    safe_name = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        district
    )

    json_file = JSON_DIR / f"{safe_name}_era5.json"

    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=4)

    print(
        f"Completed {district}: {len(weather)} daily records"
    )

    return weather


# ==========================================================
# 5. COLLECT DATA FOR ALL 25 DISTRICTS
# ==========================================================

all_weather = []
failed_districts = []

print("\n======================================")
print("STARTING WEATHER DATA COLLECTION")
print("======================================")

print("Start date:", START_DATE)
print("End date:", END_DATE)
print("Model:", MODEL)

for index, row in coordinates.iterrows():

    try:
        district_weather = collect_district_weather(row)
        all_weather.append(district_weather)

    except Exception as error:

        print(f"ERROR collecting {row['district']}: {error}")

        failed_districts.append({
            "district": row["district"],
            "error": str(error)
        })

    # Small pause between requests.
    time.sleep(0.3)


# ==========================================================
# 6. SAVE CONSOLIDATED DAILY WEATHER DATA
# ==========================================================

if all_weather:

    final_weather = pd.concat(
        all_weather,
        ignore_index=True
    )

    # Consistent column order.
    columns = [
        "district",
        "date",
        "precipitation_sum",
        "temperature_2m_mean",
        "temperature_2m_max",
        "temperature_2m_min",
        "representative_latitude",
        "representative_longitude",
        "api_grid_latitude",
        "api_grid_longitude",
        "api_grid_elevation_m",
        "weather_model",
        "weather_source",
        "timezone"
    ]

    final_weather = final_weather[columns]

    final_weather = final_weather.sort_values(
        ["district", "date"]
    ).reset_index(drop=True)

    output_file = (
        RAW_DIR /
        f"weather_daily_era5_{START_DATE}_to_{END_DATE}.csv"
    )

    final_weather.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nDaily weather CSV saved:")
    print(output_file)

else:
    print("\nNo weather data was collected.")


# ==========================================================
# 7. SAVE COLLECTION ERROR LOG
# ==========================================================

error_file = RAW_DIR / "weather_collection_errors.csv"

pd.DataFrame(
    failed_districts,
    columns=["district", "error"]
).to_csv(
    error_file,
    index=False,
    encoding="utf-8-sig"
)


# ==========================================================
# 8. COLLECTION SUMMARY
# ==========================================================

print("\n======================================")
print("WEATHER COLLECTION SUMMARY")
print("======================================")

print("Expected districts:", len(coordinates))
print("Successful districts:", len(all_weather))
print("Failed districts:", len(failed_districts))

if all_weather:

    print("Total daily records:", len(final_weather))
    print(
        "Unique districts:",
        final_weather["district"].nunique()
    )

    print(
        "First collected date:",
        final_weather["date"].min().date()
    )

    print(
        "Last collected date:",
        final_weather["date"].max().date()
    )

    print(
        "Missing values by variable:"
    )

    print(
        final_weather[DAILY_VARIABLES]
        .isna()
        .sum()
    )

print("\nError log saved to:")
print(error_file)

print("\nCollection process finished.")
