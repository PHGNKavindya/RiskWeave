
from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ============================================================
# RISKWEAVE - OPERATIONAL WEATHER ML PREDICTION TEST
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

OPERATIONAL_WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_operational_combined_2006_2026.csv"
)

EXPECTED_DISTRICTS = 25

TIMEZONE = "Asia/Colombo"


# ============================================================
# 1. PROJECT IMPORT PATH
# ============================================================

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.weather_forecasting.weather_predictions import (
    run_weather_prediction
)


# ============================================================
# 2. LOAD OPERATIONAL WEATHER DATA
# ============================================================

def load_operational_weather():

    if not OPERATIONAL_WEATHER_FILE.exists():
        raise FileNotFoundError(
            f"Operational dataset not found: "
            f"{OPERATIONAL_WEATHER_FILE}"
        )

    weather_df = pd.read_csv(
        OPERATIONAL_WEATHER_FILE
    )

    required_columns = [
        "district",
        "date",
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

    missing_columns = [
        col for col in required_columns
        if col not in weather_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing operational weather columns: "
            f"{missing_columns}"
        )

    weather_df["date"] = pd.to_datetime(
        weather_df["date"],
        errors="coerce"
    ).dt.normalize()

    weather_df["district"] = (
        weather_df["district"]
        .astype(str)
        .str.strip()
    )

    if weather_df["date"].isna().any():
        raise ValueError(
            "Invalid dates found in operational dataset."
        )

    if weather_df.duplicated(
        subset=["district", "date"]
    ).any():
        raise ValueError(
            "Duplicate district-date records found."
        )

    if weather_df["district"].nunique() != EXPECTED_DISTRICTS:
        raise ValueError(
            "Expected 25 districts in operational dataset."
        )

    print("Operational dataset loaded successfully.")
    print("Rows:", len(weather_df))
    print("Districts:", weather_df["district"].nunique())
    print("Latest date:", weather_df["date"].max().date())

    return weather_df


# ============================================================
# 3. DETERMINE FORECAST ORIGIN
# ============================================================

def get_forecast_origin():

    local_today = pd.Timestamp.now(
        tz=TIMEZONE
    ).date()

    forecast_origin = pd.Timestamp(
        local_today - pd.Timedelta(days=1)
    )

    return forecast_origin


# ============================================================
# 4. VALIDATE FORECAST ORIGIN COVERAGE
# ============================================================

def validate_forecast_origin(
    weather_df,
    forecast_origin
):

    origin_df = weather_df[
        weather_df["date"] == forecast_origin
    ]

    if origin_df["district"].nunique() != EXPECTED_DISTRICTS:

        raise ValueError(
            f"Forecast origin {forecast_origin.date()} "
            "does not contain all 25 districts."
        )

    print("\nForecast origin validation: PASSED")
    print("Forecast origin:", forecast_origin.date())
    print("Districts available:", origin_df["district"].nunique())


# ============================================================
# 5. GENERATE ML PREDICTIONS
# ============================================================

def generate_operational_predictions():

    print("\n" + "=" * 65)
    print("RISKWEAVE OPERATIONAL ML PREDICTIONS")
    print("=" * 65)

    # Load operational weather data
    weather_df = load_operational_weather()

    # Calculate yesterday's date dynamically
    forecast_origin = get_forecast_origin()

    # Validate origin data
    validate_forecast_origin(
        weather_df,
        forecast_origin
    )

    print("\nLoading existing trained models...")
    print("No model retraining will be performed.")

    # --------------------------------------------------------
    # RUN THE FOUR EXISTING MODELS
    # --------------------------------------------------------

    predictions_df = run_weather_prediction(
        weather_df=weather_df,
        forecast_origin=forecast_origin,
        save=True
    )

    if predictions_df is None:
        raise RuntimeError(
            "Prediction function returned no results."
        )

    if predictions_df.empty:
        raise ValueError(
            "No weather predictions were generated."
        )

    # --------------------------------------------------------
    # VALIDATE PREDICTION OUTPUT
    # --------------------------------------------------------

    required_prediction_columns = [
        "district",
        "forecast_origin",
        "forecast_date",
        "target",
        "horizon_days",
        "model_name",
        "predicted_value"
    ]

    missing = [
        col for col in required_prediction_columns
        if col not in predictions_df.columns
    ]

    if missing:
        raise ValueError(
            f"Prediction output missing columns: {missing}"
        )

    if predictions_df["predicted_value"].isna().any():
        raise ValueError(
            "Missing prediction values detected."
        )

    if not np.isfinite(
        predictions_df["predicted_value"].to_numpy(dtype=float)
    ).all():
        raise ValueError(
            "Infinite prediction values detected."
        )

    if predictions_df["district"].nunique() != EXPECTED_DISTRICTS:
        raise ValueError(
            "Predictions do not cover all 25 districts."
        )

    expected_targets = {
        "precipitation_sum",
        "temperature_2m_mean"
    }

    if set(predictions_df["target"].unique()) != expected_targets:
        raise ValueError(
            "Unexpected prediction targets found."
        )

    expected_horizons = {1, 7}

    if set(
        predictions_df["horizon_days"].astype(int).unique()
    ) != expected_horizons:
        raise ValueError(
            "Expected both 1-day and 7-day predictions."
        )

    # --------------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------------

    print("\n" + "=" * 65)
    print("PREDICTION RESULTS")
    print("=" * 65)

    print("Total predictions:", len(predictions_df))

    print(
        "Districts:",
        predictions_df["district"].nunique()
    )

    print(
        "Targets:",
        sorted(predictions_df["target"].unique())
    )

    print(
        "Horizons:",
        sorted(
            predictions_df["horizon_days"].unique()
        )
    )

    print("\nModel distribution:")

    print(
        predictions_df["model_name"]
        .value_counts()
        .to_string()
    )

    print("\nPrediction summary:")

    print(
        predictions_df.groupby(
            ["target", "horizon_days"]
        )["predicted_value"]
        .agg(["count", "mean", "min", "max"])
        .to_string()
    )

    print("\nSample predictions:")

    print(
        predictions_df.head(12).to_string(index=False)
    )

    print("\n" + "=" * 65)
    print("OPERATIONAL ML PREDICTION TEST COMPLETED")
    print("=" * 65)

    return predictions_df


# ============================================================
# 6. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    generate_operational_predictions()
