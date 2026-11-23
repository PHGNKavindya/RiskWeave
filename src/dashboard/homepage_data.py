
from pathlib import Path
import pandas as pd


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

WEATHER_FILE = (
    PROCESSED_DIR / "weather_operational_combined_2006_2026.csv"
)

DENGUE_FILE = (
    PROCESSED_DIR / "dengue_weekly_25_areas_2025_2026.csv"
)

ANOMALY_FILE = (
    PROCESSED_DIR
    / "environmental_anomalies"
    / "district_anomaly_summary_2026.csv"
)


# ============================================================
# 2. LOAD HOMEPAGE DATA
# ============================================================

def load_homepage_data():

    # Check whether required files exist
    required_files = [
        WEATHER_FILE,
        DENGUE_FILE,
        ANOMALY_FILE
    ]

    for file_path in required_files:
        if not file_path.exists():
            raise FileNotFoundError(
                f"Required data file not found: {file_path}"
            )

    # Load CSV files
    weather = pd.read_csv(WEATHER_FILE)
    dengue = pd.read_csv(DENGUE_FILE)
    anomaly = pd.read_csv(ANOMALY_FILE)

    # ========================================================
    # 3. WEATHER INFORMATION
    # ========================================================

    weather["date"] = pd.to_datetime(
        weather["date"],
        errors="coerce"
    )

    historical_weather = weather[
        weather["data_source"].astype(str).str.strip()
        == "Open-Meteo Historical Weather API"
    ].copy()

    if historical_weather.empty:
        raise ValueError(
            "No historical operational weather records found."
        )

    latest_weather_date = historical_weather["date"].max()

    latest_weather = historical_weather[
        historical_weather["date"] == latest_weather_date
    ].copy()

    weather_district_count = latest_weather["district"].nunique()

    temperature_mean = latest_weather[
        "temperature_2m_mean"
    ].mean()

    rainfall_mean = latest_weather[
        "precipitation_sum"
    ].mean()

    humidity_mean = latest_weather[
        "relative_humidity_2m_mean"
    ].mean()

    # ========================================================
    # 4. WEATHER FORECAST INFORMATION
    # ========================================================

    forecast_weather = weather[
        weather["data_source"].astype(str).str.strip()
        == "Open-Meteo Forecast API"
    ].copy()

    if not forecast_weather.empty:

        forecast_weather["date"] = pd.to_datetime(
            forecast_weather["date"],
            errors="coerce"
        )

        latest_forecast_date = forecast_weather["date"].max()

        latest_forecast = forecast_weather[
            forecast_weather["date"] == latest_forecast_date
        ]

        forecast_district_count = (
            latest_forecast["district"].nunique()
        )

    else:
        latest_forecast_date = pd.NaT
        forecast_district_count = 0

    # ========================================================
    # 5. DENGUE SURVEILLANCE INFORMATION
    # ========================================================

    dengue["year"] = pd.to_numeric(
        dengue["year"],
        errors="coerce"
    )

    dengue["week"] = pd.to_numeric(
        dengue["week"],
        errors="coerce"
    )

    dengue["weekly_cases"] = pd.to_numeric(
        dengue["weekly_cases"],
        errors="coerce"
    )

    valid_dengue = dengue.dropna(
        subset=["year", "week"]
    )

    if valid_dengue.empty:
        raise ValueError("No valid dengue reporting periods found.")

    latest_year = int(valid_dengue["year"].max())

    latest_year_data = valid_dengue[
        valid_dengue["year"] == latest_year
    ]

    latest_week = int(latest_year_data["week"].max())

    latest_dengue = latest_year_data[
        latest_year_data["week"] == latest_week
    ]

    dengue_total = latest_dengue["weekly_cases"].sum()

    dengue_district_count = (
        latest_dengue["district_key"].nunique()
    )

    # ========================================================
    # 6. ENVIRONMENTAL ANOMALY INFORMATION
    # ========================================================

    anomaly_district_count = anomaly["district"].nunique()

    total_anomaly_days = anomaly[
        "days_with_anomalies"
    ].sum()

    rainfall_anomalies = anomaly[
        "rainfall_anomalies"
    ].sum()

    temperature_anomalies = anomaly[
        "temperature_anomalies"
    ].sum()

    humidity_anomalies = anomaly[
        "humidity_anomalies"
    ].sum()

    # ========================================================
    # 7. RETURN HOMEPAGE DATA
    # ========================================================

    homepage_data = {

        # Weather
        "temperature_mean": temperature_mean,
        "rainfall_mean": rainfall_mean,
        "humidity_mean": humidity_mean,
        "weather_date": latest_weather_date,
        "weather_district_count": weather_district_count,

        # Weather forecast
        "forecast_date": latest_forecast_date,
        "forecast_district_count": forecast_district_count,

        # Dengue
        "dengue_total": dengue_total,
        "dengue_year": latest_year,
        "dengue_week": latest_week,
        "dengue_district_count": dengue_district_count,

        # Environmental anomalies
        "anomaly_district_count": anomaly_district_count,
        "total_anomaly_days": total_anomaly_days,
        "rainfall_anomalies": rainfall_anomalies,
        "temperature_anomalies": temperature_anomalies,
        "humidity_anomalies": humidity_anomalies
    }

    return homepage_data
