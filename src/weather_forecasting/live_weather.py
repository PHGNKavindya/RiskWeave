
from pathlib import Path
from datetime import timedelta

import requests
import pandas as pd


# ============================================================
# RISKWEAVE - LIVE AND RECENT HISTORICAL WEATHER MODULE
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

COORD_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "district_coordinates.csv"
)

HISTORICAL_WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_era5_combined_2006_2026.csv"
)

LIVE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather_live"
)

LIVE_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# OUTPUT FILES
# ------------------------------------------------------------

LIVE_WEATHER_FILE = LIVE_DIR / "live_weather_forecasts.csv"

DASHBOARD_WEATHER_FILE = (
    LIVE_DIR / "dashboard_weather_forecasts.csv"
)

YESTERDAY_WEATHER_FILE = (
    LIVE_DIR / "yesterday_completed_weather.csv"
)

RECENT_HISTORICAL_FILE = (
    LIVE_DIR / "recent_historical_weather.csv"
)


# ------------------------------------------------------------
# API ENDPOINTS
# ------------------------------------------------------------

FORECAST_API_URL = (
    "https://api.open-meteo.com/v1/forecast"
)

HISTORICAL_API_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
)


# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

FORECAST_DAYS = 8
PAST_DAYS = 1

TIMEZONE = "Asia/Colombo"

EXPECTED_DISTRICTS = 25
EXPECTED_HOURLY_RECORDS = 24

BASE_WEATHER_FEATURES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_max",
    "relative_humidity_2m_min",
    "dew_point_2m_mean",
    "wind_speed_10m_mean",
    "wind_speed_10m_max",
    "cloud_cover_mean",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration"
]


# ============================================================
# 1. COMMON HOURLY AGGREGATION
# ============================================================

def aggregate_hourly_weather(hourly_df):
    """
    Aggregate hourly observations into daily weather features.

    Uses the same aggregation definitions for historical
    and forecast API responses.
    """

    if "time" not in hourly_df.columns:
        raise ValueError("Hourly time column is missing.")

    hourly_df = hourly_df.copy()

    hourly_df["date"] = pd.to_datetime(
        hourly_df["time"],
        errors="coerce"
    ).dt.normalize()

    hourly_df = hourly_df.dropna(subset=["date"])

    hourly_variables = [
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "wind_speed_10m",
        "cloud_cover"
    ]

    missing = [
        col for col in hourly_variables
        if col not in hourly_df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing hourly variables: {missing}"
        )

    for col in hourly_variables:
        hourly_df[col] = pd.to_numeric(
            hourly_df[col],
            errors="coerce"
        )

    summary = (
        hourly_df.groupby("date")
        .agg(
            temperature_2m_mean=(
                "temperature_2m",
                "mean"
            ),
            relative_humidity_2m_mean=(
                "relative_humidity_2m",
                "mean"
            ),
            relative_humidity_2m_max=(
                "relative_humidity_2m",
                "max"
            ),
            relative_humidity_2m_min=(
                "relative_humidity_2m",
                "min"
            ),
            dew_point_2m_mean=(
                "dew_point_2m",
                "mean"
            ),
            wind_speed_10m_mean=(
                "wind_speed_10m",
                "mean"
            ),
            cloud_cover_mean=(
                "cloud_cover",
                "mean"
            ),
            hourly_observation_count=(
                "temperature_2m",
                "count"
            )
        )
        .reset_index()
    )

    return summary


# ============================================================
# 2. COMMON DAILY DATA PREPARATION
# ============================================================

def prepare_daily_weather(data, district, data_source):
    """
    Convert an API response into a standard daily dataset.
    """

    if "daily" not in data or "hourly" not in data:
        raise ValueError(
            "Daily or hourly weather data missing from API."
        )

    daily_df = pd.DataFrame(data["daily"])

    hourly_df = pd.DataFrame(data["hourly"])

    if "time" not in daily_df.columns:
        raise ValueError("Daily time column is missing.")

    daily_df["date"] = pd.to_datetime(
        daily_df["time"],
        errors="coerce"
    ).dt.normalize()

    daily_df = daily_df.drop(
        columns=["time"]
    )

    hourly_summary = aggregate_hourly_weather(
        hourly_df
    )

    result = daily_df.merge(
        hourly_summary,
        on="date",
        how="left"
    )

    result["district"] = str(
        district["district"]
    ).strip()

    result["data_source"] = data_source

    result["retrieved_at"] = (
        pd.Timestamp.now(
            tz=TIMEZONE
        ).strftime("%Y-%m-%d %H:%M:%S")
    )

    result = result.sort_values(
        "date"
    ).reset_index(drop=True)

    return result


# ============================================================
# 3. COLLECT FORECAST API DATA
# ============================================================

def collect_district_weather(district):
    """
    Collect yesterday and future weather for one district.

    Source:
        Open-Meteo Forecast API
    """

    params = {
        "latitude": float(district["latitude"]),
        "longitude": float(district["longitude"]),

        "daily": ",".join([
            "precipitation_sum",
            "rain_sum",
            "precipitation_hours",
            "temperature_2m_max",
            "temperature_2m_min",
            "shortwave_radiation_sum",
            "et0_fao_evapotranspiration",
            "wind_speed_10m_max",
            "wind_direction_10m_dominant"
        ]),

        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "wind_speed_10m",
            "cloud_cover"
        ]),

        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": TIMEZONE
    }

    response = requests.get(
        FORECAST_API_URL,
        params=params,
        timeout=90
    )

    response.raise_for_status()

    result = prepare_daily_weather(
        response.json(),
        district,
        "Open-Meteo Forecast API"
    )

    return result


# ============================================================
# 4. LOAD HISTORICAL DATA COVERAGE
# ============================================================

def get_historical_coverage():
    """
    Read the existing ERA5 dataset to identify its latest date.

    The original ERA5 dataset is read only.
    It is never modified by this module.
    """

    if not HISTORICAL_WEATHER_FILE.exists():
        raise FileNotFoundError(
            "Historical ERA5 dataset not found: "
            f"{HISTORICAL_WEATHER_FILE}"
        )

    history = pd.read_csv(
        HISTORICAL_WEATHER_FILE,
        usecols=["district", "date"]
    )

    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce"
    )

    history = history.dropna(
        subset=["district", "date"]
    )

    history["district"] = (
        history["district"]
        .astype(str)
        .str.strip()
    )

    districts = set(history["district"].unique())

    if len(districts) != EXPECTED_DISTRICTS:
        raise ValueError(
            "Historical dataset does not contain "
            f"exactly {EXPECTED_DISTRICTS} districts. "
            f"Found: {len(districts)}"
        )

    latest_date = history["date"].max().normalize()

    print("\nHistorical ERA5 coverage:")
    print("Latest date:", latest_date.date())
    print("Districts:", len(districts))

    return latest_date


# ============================================================
# 5. COLLECT RECENT HISTORICAL DATA
# ============================================================

def collect_historical_district_weather(
    district,
    start_date,
    end_date
):
    """
    Retrieve recent historical weather from the
    Open-Meteo Historical Weather API.

    The API's returned coverage is validated later.
    """

    params = {
        "latitude": float(district["latitude"]),
        "longitude": float(district["longitude"]),

        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),

        "daily": ",".join([
            "precipitation_sum",
            "rain_sum",
            "precipitation_hours",
            "temperature_2m_max",
            "temperature_2m_min",
            "shortwave_radiation_sum",
            "et0_fao_evapotranspiration",
            "wind_speed_10m_max",
            "wind_direction_10m_dominant"
        ]),

        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "wind_speed_10m",
            "cloud_cover"
        ]),

        "timezone": TIMEZONE
    }

    response = requests.get(
        HISTORICAL_API_URL,
        params=params,
        timeout=120
    )

    response.raise_for_status()

    result = prepare_daily_weather(
        response.json(),
        district,
        "Open-Meteo Historical Weather API"
    )

    return result


# ============================================================
# 6. LOAD DISTRICT COORDINATES
# ============================================================

def load_district_coordinates():
    """
    Load and validate the 25 district coordinates.
    """

    if not COORD_FILE.exists():
        raise FileNotFoundError(
            f"Coordinate file not found: {COORD_FILE}"
        )

    district_coords = pd.read_csv(
        COORD_FILE
    )

    required_columns = {
        "district",
        "latitude",
        "longitude"
    }

    if not required_columns.issubset(
        district_coords.columns
    ):
        raise ValueError(
            "Coordinate file must contain: "
            f"{required_columns}"
        )

    district_coords["district"] = (
        district_coords["district"]
        .astype(str)
        .str.strip()
    )

    district_coords["latitude"] = pd.to_numeric(
        district_coords["latitude"],
        errors="coerce"
    )

    district_coords["longitude"] = pd.to_numeric(
        district_coords["longitude"],
        errors="coerce"
    )

    if district_coords[
        ["district", "latitude", "longitude"]
    ].isna().any().any():
        raise ValueError(
            "Invalid district names or coordinates found."
        )

    if district_coords["district"].duplicated().any():
        raise ValueError(
            "Duplicate district names found."
        )

    if len(district_coords) != EXPECTED_DISTRICTS:
        raise ValueError(
            f"Expected {EXPECTED_DISTRICTS} districts, "
            f"found {len(district_coords)}."
        )

    return district_coords


# ============================================================
# 7. VALIDATE RECENT HISTORICAL DATA
# ============================================================

def validate_recent_historical_data(
    historical_df,
    expected_dates,
    expected_districts
):
    """
    Validate date and district completeness.

    Does not fill unavailable dates.
    """

    if historical_df.empty:
        raise ValueError(
            "Historical API returned no records."
        )

    historical_df = historical_df.copy()

    historical_df["date"] = pd.to_datetime(
        historical_df["date"],
        errors="coerce"
    ).dt.normalize()

    if historical_df["date"].isna().any():
        raise ValueError(
            "Invalid dates in historical API data."
        )

    if historical_df.duplicated(
        subset=["district", "date"]
    ).any():
        raise ValueError(
            "Duplicate district-date records "
            "in historical API data."
        )

    expected_pairs = {
        (district, date)
        for district in expected_districts
        for date in expected_dates
    }

    actual_pairs = set(
        zip(
            historical_df["district"],
            historical_df["date"]
        )
    )

    missing_pairs = expected_pairs - actual_pairs

    if missing_pairs:

        missing_summary = pd.DataFrame(
            list(missing_pairs),
            columns=["district", "date"]
        )

        print("\nUnavailable historical records:")
        print(
            missing_summary.sort_values(
                ["district", "date"]
            ).to_string(index=False)
        )

        raise ValueError(
            f"Historical API did not return "
            f"{len(missing_pairs)} expected district-date records. "
            "Do not proceed with incomplete data."
        )

    # Check required ML features
    missing_columns = [
        col for col in BASE_WEATHER_FEATURES
        if col not in historical_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing historical ML features: {missing_columns}"
        )

    for col in BASE_WEATHER_FEATURES:
        historical_df[col] = pd.to_numeric(
            historical_df[col],
            errors="coerce"
        )

    missing_values = (
        historical_df[BASE_WEATHER_FEATURES]
        .isna()
        .sum()
    )

    missing_values = missing_values[
        missing_values > 0
    ]

    if not missing_values.empty:
        raise ValueError(
            "Missing values in historical ML features:\n"
            f"{missing_values}"
        )

    if (
        historical_df["hourly_observation_count"] 
        != EXPECTED_HOURLY_RECORDS
    ).any():
        raise ValueError(
            "Incomplete hourly historical observations. "
            "Expected 24 hourly temperature observations per day."
        )

    print("\nRecent historical validation successful.")
    print("Districts:", len(expected_districts))
    print("Dates:", len(expected_dates))
    print("Records:", len(historical_df))

    return historical_df.sort_values(
        ["district", "date"]
    ).reset_index(drop=True)


# ============================================================
# 8. EXTRACT YESTERDAY'S COMPLETED WEATHER
# ============================================================

def extract_yesterday_weather(live_df):
    """
    Extract yesterday's completed API weather for 25 districts.
    """

    yesterday = (
        pd.Timestamp.now(tz=TIMEZONE).date()
        - timedelta(days=1)
    )

    yesterday_df = live_df[
        live_df["date"].dt.date == yesterday
    ].copy()

    if yesterday_df.empty:
        raise ValueError(
            f"No weather data found for {yesterday}."
        )

    if yesterday_df["district"].nunique() != EXPECTED_DISTRICTS:
        raise ValueError(
            "Yesterday's data does not contain all 25 districts."
        )

    if yesterday_df.duplicated(
        subset=["district", "date"]
    ).any():
        raise ValueError(
            "Duplicate district-date records in yesterday's data."
        )

    for col in BASE_WEATHER_FEATURES:
        if col not in yesterday_df.columns:
            raise ValueError(
                f"Missing yesterday's ML feature: {col}"
            )

        yesterday_df[col] = pd.to_numeric(
            yesterday_df[col],
            errors="coerce"
        )

    if yesterday_df[
        BASE_WEATHER_FEATURES
    ].isna().any().any():
        raise ValueError(
            "Yesterday's API data contains missing ML features."
        )

    if (
        yesterday_df["hourly_observation_count"]
        != EXPECTED_HOURLY_RECORDS
    ).any():
        raise ValueError(
            "Yesterday's hourly observations are incomplete."
        )

    return yesterday_df.sort_values(
        "district"
    ).reset_index(drop=True)


# ============================================================
# 9. VALIDATE FUTURE DASHBOARD DATA
# ============================================================


def validate_dashboard_forecasts(
    dashboard_df,
    tomorrow,
    seventh_day
):
    """
    Validate future forecast coverage and weather features
    for all 25 districts.
    """

    if dashboard_df.empty:
        raise ValueError(
            "Dashboard forecast dataset is empty."
        )

    dashboard_df = dashboard_df.copy()

    dashboard_df["date"] = pd.to_datetime(
        dashboard_df["date"],
        errors="coerce"
    ).dt.normalize()

    if dashboard_df["date"].isna().any():
        raise ValueError(
            "Invalid dates found in dashboard forecasts."
        )

    expected_dates = pd.date_range(
        tomorrow,
        seventh_day,
        freq="D"
    )

    expected_districts = set(
        load_district_coordinates()["district"]
    )

    actual_districts = set(
        dashboard_df["district"].astype(str).str.strip()
    )

    if actual_districts != expected_districts:
        raise ValueError(
            "Dashboard forecast district coverage is incorrect. "
            f"Expected {len(expected_districts)} districts, "
            f"found {len(actual_districts)}."
        )

    if dashboard_df.duplicated(
        subset=["district", "date"]
    ).any():
        raise ValueError(
            "Duplicate district-date records in dashboard forecasts."
        )

    expected_pairs = {
        (district, date)
        for district in expected_districts
        for date in expected_dates
    }

    actual_pairs = set(
        zip(
            dashboard_df["district"].astype(str).str.strip(),
            dashboard_df["date"]
        )
    )

    missing_pairs = expected_pairs - actual_pairs

    unexpected_pairs = actual_pairs - expected_pairs

    if missing_pairs or unexpected_pairs:
        raise ValueError(
            "Dashboard forecast date coverage is incomplete. "
            f"Missing records: {len(missing_pairs)}. "
            f"Unexpected records: {len(unexpected_pairs)}."
        )

    if len(dashboard_df) != 175:
        raise ValueError(
            f"Expected 175 dashboard records, "
            f"found {len(dashboard_df)}."
        )

    # Validate all 13 ML weather features.
    missing_columns = [
        col for col in BASE_WEATHER_FEATURES
        if col not in dashboard_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing forecast ML features: {missing_columns}"
        )

    for col in BASE_WEATHER_FEATURES:
        dashboard_df[col] = pd.to_numeric(
            dashboard_df[col],
            errors="coerce"
        )

    missing_values = (
        dashboard_df[BASE_WEATHER_FEATURES]
        .isna()
        .sum()
    )

    missing_values = missing_values[
        missing_values > 0
    ]

    if not missing_values.empty:
        raise ValueError(
            "Missing values in forecast ML features:\n"
            f"{missing_values}"
        )

    # Check hourly coverage.
    if "hourly_observation_count" not in dashboard_df.columns:
        raise ValueError(
            "Hourly observation count is missing."
        )

    if (
        dashboard_df["hourly_observation_count"]
        != EXPECTED_HOURLY_RECORDS
    ).any():
        raise ValueError(
            "Incomplete hourly forecast observations. "
            "Expected 24 hourly temperature observations per day."
        )

    print("\nDashboard forecast validation successful.")
    print("Districts:", len(actual_districts))
    print("Forecast dates:", len(expected_dates))
    print("Validated records:", len(dashboard_df))

    return dashboard_df

    """
    Validate seven future forecast days for 25 districts.
    """

    expected_dates = pd.date_range(
        tomorrow,
        seventh_day,
        freq="D"
    )

    expected_pairs = {
        (district, date)
        for district in dashboard_df["district"].unique()
        for date in expected_dates
    }

    actual_pairs = set(
        zip(
            dashboard_df["district"],
            dashboard_df["date"]
        )
    )

    if (
        dashboard_df["district"].nunique()
        != EXPECTED_DISTRICTS
    ):
        raise ValueError(
            "Dashboard forecast does not contain 25 districts."
        )

    if len(dashboard_df) != 175:
        raise ValueError(
            f"Expected 175 dashboard records, "
            f"found {len(dashboard_df)}."
        )

    if expected_pairs != actual_pairs:
        raise ValueError(
            "Dashboard forecast date coverage is incomplete."
        )


# ============================================================
# 10. SAVE ALL WEATHER DATASETS
# ============================================================

def save_weather_files(
    live_df,
    dashboard_df,
    yesterday_df,
    recent_historical_df
):
    """
    Save datasets after all validation has succeeded.
    """

    LIVE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    live_df.to_csv(
        LIVE_WEATHER_FILE,
        index=False
    )

    dashboard_df.to_csv(
        DASHBOARD_WEATHER_FILE,
        index=False
    )

    yesterday_df.to_csv(
        YESTERDAY_WEATHER_FILE,
        index=False
    )

    recent_historical_df.to_csv(
        RECENT_HISTORICAL_FILE,
        index=False
    )

    print("\nWeather datasets saved:")
    print("Live forecasts:", LIVE_WEATHER_FILE)
    print("Dashboard forecasts:", DASHBOARD_WEATHER_FILE)
    print("Yesterday's weather:", YESTERDAY_WEATHER_FILE)
    print("Recent historical data:", RECENT_HISTORICAL_FILE)


# ============================================================
# 11. MAIN UPDATE FUNCTION
# ============================================================

def update_live_weather():
    """
    Update recent historical and live forecast weather.

    The original ERA5 dataset is never overwritten.

    Outputs:
        1. live_weather_forecasts.csv
        2. dashboard_weather_forecasts.csv
        3. yesterday_completed_weather.csv
        4. recent_historical_weather.csv
    """

    print("\n" + "=" * 65)
    print("RISKWEAVE WEATHER DATA UPDATE")
    print("=" * 65)

    district_coords = load_district_coordinates()

    # --------------------------------------------------------
    # DETERMINE MISSING HISTORICAL DATE RANGE
    # --------------------------------------------------------

    latest_era5_date = get_historical_coverage()

    # Use a timezone-naive date to match the ERA5 dataset.
    today = pd.Timestamp(
        pd.Timestamp.now(tz=TIMEZONE).date()
    )

    yesterday = today - pd.Timedelta(days=1)

    # Historical API retrieves dates after ERA5 coverage,
    # excluding yesterday because the Forecast API supplies it.
    historical_start = (
        latest_era5_date + pd.Timedelta(days=1)
    )

    historical_end = (
        yesterday - pd.Timedelta(days=1)
    )

    if historical_start <= historical_end:
        expected_dates = pd.date_range(
            start=historical_start,
            end=historical_end,
            freq="D"
        )
    else:
        expected_dates = pd.DatetimeIndex([])

    recent_historical_records = []

    # --------------------------------------------------------
    # RETRIEVE RECENT HISTORICAL WEATHER
    # --------------------------------------------------------

    if len(expected_dates) > 0:

        print("\nRecent historical retrieval:")
        print("Start:", historical_start.date())
        print("End:", historical_end.date())

        failures = []

        for _, district in district_coords.iterrows():

            name = district["district"]

            try:

                district_df = (
                    collect_historical_district_weather(
                        district,
                        historical_start,
                        historical_end
                    )
                )

                recent_historical_records.append(
                    district_df
                )

                print(
                    f"Historical data collected: {name}"
                )

            except Exception as error:

                failures.append({
                    "district": name,
                    "error": str(error)
                })

                print(
                    f"HISTORICAL FAILED: {name}: {error}"
                )

        if failures:
            print("\nHistorical API failures:")
            print(
                pd.DataFrame(failures).to_string(
                    index=False
                )
            )

            raise RuntimeError(
                "Recent historical retrieval failed. "
                "Existing output files were not updated."
            )

        recent_historical_df = pd.concat(
            recent_historical_records,
            ignore_index=True
        )

        recent_historical_df["date"] = pd.to_datetime(
            recent_historical_df["date"]
        ).dt.normalize()

        recent_historical_df = (
            validate_recent_historical_data(
                recent_historical_df,
                expected_dates,
                set(district_coords["district"])
            )
        )

    else:

        print(
            "\nNo historical gap requires retrieval."
        )

        recent_historical_df = pd.DataFrame(
            columns=[
                "date",
                "district",
                *BASE_WEATHER_FEATURES,
                "data_source",
                "retrieved_at"
            ]
        )

    # --------------------------------------------------------
    # RETRIEVE FORECAST API DATA
    # --------------------------------------------------------

    print("\nCollecting live forecast data...")

    live_records = []
    failures = []

    for _, district in district_coords.iterrows():

        name = district["district"]

        try:

            district_df = collect_district_weather(
                district
            )

            live_records.append(
                district_df
            )

            print(
                f"Forecast data collected: {name}"
            )

        except Exception as error:

            failures.append({
                "district": name,
                "error": str(error)
            })

            print(
                f"FORECAST FAILED: {name}: {error}"
            )

    if failures:

        print("\nForecast API failures:")
        print(
            pd.DataFrame(failures).to_string(
                index=False
            )
        )

        raise RuntimeError(
            "Forecast retrieval failed. "
            "Existing output files were not updated."
        )

    live_df = pd.concat(
        live_records,
        ignore_index=True
    )

    live_df["date"] = pd.to_datetime(
        live_df["date"]
    ).dt.normalize()

    live_df = live_df.sort_values(
        ["district", "date"]
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # EXTRACT YESTERDAY'S DATA
    # --------------------------------------------------------

    yesterday_df = extract_yesterday_weather(
        live_df
    )

    # --------------------------------------------------------
    # PREPARE DASHBOARD FORECAST
    # --------------------------------------------------------

    tomorrow = today + pd.Timedelta(days=1)

    seventh_day = today + pd.Timedelta(days=7)

    dashboard_df = live_df[
        (
            live_df["date"] >= tomorrow
        )
        &
        (
            live_df["date"] <= seventh_day
        )
    ].copy()

    validate_dashboard_forecasts(
        dashboard_df,
        tomorrow,
        seventh_day
    )

    # --------------------------------------------------------
    # SAVE DATASETS AFTER ALL VALIDATION
    # --------------------------------------------------------

    save_weather_files(
        live_df,
        dashboard_df,
        yesterday_df,
        recent_historical_df
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 65)
    print("RISKWEAVE WEATHER UPDATE COMPLETED")
    print("=" * 65)

    print(
        "Districts:",
        district_coords["district"].nunique()
    )

    print(
        "Historical backfill records:",
        len(recent_historical_df)
    )

    if not recent_historical_df.empty:
        print(
            "Historical backfill period:",
            recent_historical_df["date"].min().date(),
            "to",
            recent_historical_df["date"].max().date()
        )

    print(
        "Yesterday's records:",
        len(yesterday_df)
    )

    print(
        "Yesterday's date:",
        yesterday_df["date"].iloc[0].date()
    )

    print(
        "Dashboard forecast records:",
        len(dashboard_df)
    )

    print(
        "Dashboard forecast period:",
        tomorrow.date(),
        "to",
        seventh_day.date()
    )

    print("\nAll weather datasets passed validation.")

    return {
        "live": live_df,
        "dashboard": dashboard_df,
        "yesterday": yesterday_df,
        "recent_historical": recent_historical_df
    }


# ============================================================
# 12. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    update_live_weather()
