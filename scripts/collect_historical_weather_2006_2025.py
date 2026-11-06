"""
RiskWeave - Historical ERA5 Daily Weather Collection
====================================================

Run from VS Code terminal:
    python scripts/collect_historical_weather_2006_2025.py

The script:
- Reads the existing 25 district representative coordinates.
- Collects daily ERA5 weather from Open-Meteo.
- Saves each district CSV and original JSON response separately.
- Skips districts that already have complete, valid CSV files.
- Rebuilds the consolidated master CSV after collection.
- Stops safely if Open-Meteo continues returning HTTP 429.

Required packages:
    pip install pandas requests
"""

import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from email.utils import parsedate_to_datetime

import pandas as pd
import requests


# ============================================================
# 1. PROJECT PATHS AND COLLECTION SETTINGS
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parents[1]

COORDINATES_FILE = (
    PROJECT_DIR / "data" / "reference" / "district_coordinates.csv"
)

RAW_DIR = PROJECT_DIR / "data" / "raw"
HISTORICAL_DIR = RAW_DIR / "weather_era5_2006_2025"

DISTRICT_CSV_DIR = HISTORICAL_DIR / "district_csv"
JSON_DIR = HISTORICAL_DIR / "json"

for folder in (HISTORICAL_DIR, DISTRICT_CSV_DIR, JSON_DIR):
    folder.mkdir(parents=True, exist_ok=True)

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2006-12-23"
END_DATE = "2025-12-19"
TIMEZONE = "Asia/Colombo"
MODEL = "era5"

# Pause between successful district requests.
DELAY_BETWEEN_REQUESTS_SECONDS = 30

# On HTTP 429, wait at least this long if Retry-After is not supplied.
RATE_LIMIT_WAIT_SECONDS = 300
MAX_RATE_LIMIT_RETRIES = 3

DAILY_VARIABLES = [
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_max",
    "relative_humidity_2m_min",
    "dew_point_2m_mean",
    "wind_speed_10m_mean",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "cloud_cover_mean",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
]

EXPECTED_DATES = pd.date_range(START_DATE, END_DATE, freq="D")
EXPECTED_DAYS = len(EXPECTED_DATES)

CSV_COLUMNS = (
    ["district", "date"]
    + DAILY_VARIABLES
    + [
        "representative_latitude",
        "representative_longitude",
        "api_grid_latitude",
        "api_grid_longitude",
        "api_grid_elevation_m",
        "weather_model",
        "weather_source",
        "timezone",
    ]
)


# ============================================================
# 2. SMALL HELPER FUNCTIONS
# ============================================================

def safe_filename(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name)).strip("_")


def district_csv_path(district):
    return DISTRICT_CSV_DIR / (
        f"{safe_filename(district)}_era5_2006_2025.csv"
    )


def district_json_path(district):
    return JSON_DIR / (
        f"{safe_filename(district)}_era5_2006_2025.json"
    )


def is_complete_saved_file(path, district):
    """Return True only if an existing district CSV has full date coverage."""
    if not path.exists():
        return False

    try:
        saved = pd.read_csv(path)

        required = set(CSV_COLUMNS)
        if not required.issubset(saved.columns):
            return False

        saved["date"] = pd.to_datetime(saved["date"], errors="coerce")

        if saved["district"].nunique() != 1:
            return False

        if str(saved["district"].iloc[0]) != str(district):
            return False

        actual_dates = pd.DatetimeIndex(saved["date"].dropna()).sort_values()

        return (
            len(saved) == EXPECTED_DAYS
            and saved["date"].notna().all()
            and actual_dates.equals(EXPECTED_DATES)
            and not saved["date"].duplicated().any()
        )

    except Exception:
        return False


def get_retry_after_seconds(response):
    """Read Retry-After as seconds or an HTTP date, if provided."""
    value = response.headers.get("Retry-After")

    if not value:
        return None

    try:
        return max(0, int(value))
    except ValueError:
        try:
            retry_date = parsedate_to_datetime(value)
            now = pd.Timestamp.now(tz="UTC").to_pydatetime()
            if retry_date.tzinfo is None:
                retry_date = retry_date.replace(tzinfo=now.tzinfo)
            return max(0, int((retry_date - now).total_seconds()))
        except Exception:
            return None


def request_weather(session, params, district):
    """Request one district. Persistent rate limiting stops the run safely."""
    rate_limit_attempts = 0

    while True:
        response = session.get(API_URL, params=params, timeout=180)

        if response.status_code == 429:
            rate_limit_attempts += 1

            if rate_limit_attempts > MAX_RATE_LIMIT_RETRIES:
                raise RuntimeError(
                    "Open-Meteo continued returning HTTP 429. "
                    "The script is stopping safely. Run it again later; "
                    "completed district files will be skipped."
                )

            wait_seconds = get_retry_after_seconds(response)
            if wait_seconds is None:
                wait_seconds = RATE_LIMIT_WAIT_SECONDS

            print(
                f"HTTP 429 for {district}. "
                f"Waiting {wait_seconds} seconds "
                f"(rate-limit retry {rate_limit_attempts}/"
                f"{MAX_RATE_LIMIT_RETRIES}).",
                flush=True,
            )
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        payload = response.json()

        if payload.get("error"):
            raise RuntimeError(payload.get("reason", "Open-Meteo API error"))

        return payload


# ============================================================
# 3. COLLECT ONE DISTRICT
# ============================================================

def collect_one_district(session, row):
    district = str(row["district"])
    latitude = float(row["latitude"])
    longitude = float(row["longitude"])

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "wind_speed_unit": "kmh",
        "models": MODEL,
    }

    print(f"\nRequesting {district}...", flush=True)

    payload = request_weather(session, params, district)

    if "daily" not in payload:
        raise RuntimeError(f"No daily data returned for {district}")

    daily = payload["daily"]

    missing_variables = [
        variable for variable in DAILY_VARIABLES
        if variable not in daily
    ]
    if missing_variables:
        raise RuntimeError(
            f"{district}: API response missing {missing_variables}"
        )

    weather = pd.DataFrame(daily)
    weather["date"] = pd.to_datetime(weather.pop("time"), errors="coerce")

    if weather["date"].isna().any():
        raise RuntimeError(f"{district}: invalid dates in API response")

    actual_dates = pd.DatetimeIndex(weather["date"]).sort_values()
    if not actual_dates.equals(EXPECTED_DATES):
        raise RuntimeError(
            f"{district}: expected {EXPECTED_DAYS} dates, "
            f"received {len(weather)} dates or an unexpected date sequence"
        )

    weather["district"] = district
    weather["representative_latitude"] = latitude
    weather["representative_longitude"] = longitude
    weather["api_grid_latitude"] = payload.get("latitude")
    weather["api_grid_longitude"] = payload.get("longitude")
    weather["api_grid_elevation_m"] = payload.get("elevation")
    weather["weather_model"] = MODEL
    weather["weather_source"] = "Open-Meteo Historical Weather API"
    weather["timezone"] = TIMEZONE

    weather = weather[CSV_COLUMNS].sort_values("date").reset_index(drop=True)

    # Save raw JSON response and district CSV checkpoint.
    with open(district_json_path(district), "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    csv_path = district_csv_path(district)
    weather.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(
        f"Saved {district}: {len(weather):,} daily rows",
        flush=True,
    )

    return weather


# ============================================================
# 4. REBUILD MASTER CSV FROM ALL COMPLETE DISTRICT FILES
# ============================================================

def rebuild_master(coordinates):
    frames = []
    incomplete = []

    for district in coordinates["district"].astype(str):
        path = district_csv_path(district)

        if is_complete_saved_file(path, district):
            frame = pd.read_csv(path)
            frame["date"] = pd.to_datetime(frame["date"])
            frames.append(frame)
        else:
            incomplete.append(district)

    if frames:
        master = pd.concat(frames, ignore_index=True)
        master = master[CSV_COLUMNS].sort_values(
            ["district", "date"]
        ).reset_index(drop=True)

        master_path = HISTORICAL_DIR / (
            "weather_daily_era5_2006-12-23_to_2025-12-19.csv"
        )
        master.to_csv(master_path, index=False, encoding="utf-8-sig")

        print("\nMaster CSV updated:", master_path, flush=True)
        print("Master shape:", master.shape, flush=True)
        print("Complete districts:", master["district"].nunique(), flush=True)
    else:
        print("\nNo complete district files available for master CSV yet.")

    if incomplete:
        print("\nDistricts still incomplete:")
        print(", ".join(incomplete))

    return incomplete


# ============================================================
# 5. MAIN
# ============================================================

def main():
    print("RISKWEAVE HISTORICAL WEATHER COLLECTION", flush=True)
    print("Project:", PROJECT_DIR, flush=True)
    print("Period:", START_DATE, "to", END_DATE, flush=True)
    print("Expected daily rows per district:", EXPECTED_DAYS, flush=True)

    if not COORDINATES_FILE.exists():
        raise FileNotFoundError(
            f"Coordinates file not found: {COORDINATES_FILE}"
        )

    coordinates = pd.read_csv(COORDINATES_FILE)

    required_columns = {"district", "latitude", "longitude"}
    if not required_columns.issubset(coordinates.columns):
        raise ValueError(
            "district_coordinates.csv must contain district, latitude, longitude"
        )

    if coordinates["district"].duplicated().any():
        raise ValueError("Duplicate district names in coordinate file.")

    if coordinates[list(required_columns)].isna().any().any():
        raise ValueError("Missing district names or coordinates.")

    print("Districts in coordinate file:", len(coordinates), flush=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "RiskWeave-Research-Project/1.0"
    })

    failed = []
    completed_this_run = 0

    for _, row in coordinates.iterrows():
        district = str(row["district"])
        csv_path = district_csv_path(district)

        if is_complete_saved_file(csv_path, district):
            print(f"SKIP {district}: complete file already exists", flush=True)
            continue

        try:
            collect_one_district(session, row)
            completed_this_run += 1

            # Be considerate of the public API.
            time.sleep(DELAY_BETWEEN_REQUESTS_SECONDS)

        except RuntimeError as error:
            message = str(error)
            print(f"\nSTOP: {message}", flush=True)
            failed.append({"district": district, "error": message})

            if "HTTP 429" in message:
                break

        except Exception as error:
            print(f"FAILED {district}: {error}", flush=True)
            failed.append({"district": district, "error": str(error)})

            # Pause before moving to the next district after a failure.
            time.sleep(60)

    # Save error log, including failures from this run.
    error_path = HISTORICAL_DIR / "weather_collection_errors.csv"
    pd.DataFrame(failed, columns=["district", "error"]).to_csv(
        error_path, index=False, encoding="utf-8-sig"
    )

    incomplete = rebuild_master(coordinates)

    print("\nCOLLECTION SUMMARY", flush=True)
    print("New districts collected this run:", completed_this_run, flush=True)
    print("Incomplete districts remaining:", len(incomplete), flush=True)
    print("Error log:", error_path, flush=True)

    if not incomplete:
        print(
            "\nAll districts have complete daily date coverage.",
            flush=True,
        )
    else:
        print(
            "\nRun this script again later to resume. "
            "Complete district files will be skipped.",
            flush=True,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\nInterrupted by user. Saved district files are preserved. "
            "Run the script again later to resume.",
            flush=True,
        )
        sys.exit(1)
