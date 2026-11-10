
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


# ============================================================
# 1. PROJECT PATHS AND MODEL CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "weather_forecasting"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "weather_forecasting"
    / "operational"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "latest_ml_weather_predictions.csv"
)

MODEL_FILES = {
    "rainfall_1day": "precipitation_sum_1day_model.joblib",
    "rainfall_7day": "precipitation_sum_7day_model.joblib",
    "temperature_1day": "temperature_2m_mean_1day_model.joblib",
    "temperature_7day": "temperature_2m_mean_7day_model.joblib",
}


# ============================================================
# 2. BASE WEATHER FEATURES
# Must match the training notebook
# ============================================================

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
    "et0_fao_evapotranspiration",
]

LAG_DAYS = [1, 2, 3, 7, 14, 28]

ROLLING_VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
]

ROLLING_WINDOWS = [7, 14, 30]


# ============================================================
# 3. LOAD TRAINED MODELS
# ============================================================

def load_weather_models():
    """
    Load the four previously trained weather models.

    No model training takes place here.
    """

    models = {}

    for model_name, filename in MODEL_FILES.items():

        model_path = MODEL_DIR / filename

        if not model_path.exists():
            raise FileNotFoundError(
                f"Weather model not found: {model_path}"
            )

        artifact = joblib.load(model_path)

        required_keys = [
            "model",
            "preprocessor",
            "target",
            "horizon_days",
            "model_name",
            "feature_columns",
            "categorical_features",
            "numerical_features",
        ]

        missing_keys = [
            key for key in required_keys
            if key not in artifact
        ]

        if missing_keys:
            raise ValueError(
                f"Invalid model artifact {filename}. "
                f"Missing keys: {missing_keys}"
            )

        models[model_name] = artifact

    return models


# ============================================================
# 4. INSPECT TRAINED MODELS
# ============================================================

def inspect_weather_models():
    """
    Display metadata and expected input features.
    """

    models = load_weather_models()

    for model_name, artifact in models.items():

        print("\n" + "=" * 65)
        print(model_name.upper())
        print("=" * 65)

        print("Target:", artifact["target"])
        print("Horizon:", artifact["horizon_days"])
        print("Algorithm:", artifact["model_name"])

        print(
            "Expected feature count:",
            len(artifact["feature_columns"])
        )

        print(
            "Categorical features:",
            artifact["categorical_features"]
        )

        print(
            "Numerical feature count:",
            len(artifact["numerical_features"])
        )

    return models


# ============================================================
# 5. VALIDATE HISTORICAL WEATHER DATA
# ============================================================

def validate_weather_data(weather_df):
    """
    Validate the historical and latest daily weather data
    before feature engineering.
    """

    if weather_df.empty:
        raise ValueError(
            "Weather dataset is empty."
        )

    required_columns = (
        ["district", "date"]
        + BASE_WEATHER_FEATURES
    )

    missing_columns = [
        col for col in required_columns
        if col not in weather_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing weather columns: {missing_columns}"
        )

    weather_df = weather_df.copy()

    weather_df["date"] = pd.to_datetime(
        weather_df["date"],
        errors="coerce"
    ).dt.normalize()

    weather_df["district"] = (
        weather_df["district"]
        .astype(str)
        .str.strip()
    )

    weather_df = weather_df.dropna(
        subset=["date", "district"]
    )

    if weather_df["district"].eq("").any():
        raise ValueError(
            "Empty district names found."
        )

    # Convert weather variables to numeric
    for col in BASE_WEATHER_FEATURES:

        weather_df[col] = pd.to_numeric(
            weather_df[col],
            errors="coerce"
        )

    # Reject duplicate district-date records
    duplicates = weather_df.duplicated(
        subset=["district", "date"],
        keep=False
    )

    if duplicates.any():

        duplicate_records = weather_df.loc[
            duplicates,
            ["district", "date"]
        ]

        raise ValueError(
            "Duplicate district-date records detected:\n"
            f"{duplicate_records.head(10)}"
        )

    return weather_df.sort_values(
        ["district", "date"]
    ).reset_index(drop=True)


# ============================================================
# 6. CREATE FEATURES FOR A SPECIFIC FORECAST ORIGIN
# ============================================================

def create_latest_weather_features(
    weather_df,
    forecast_origin
):
    """
    Create historical features for a specified forecast origin.

    Feature definitions match the training notebook:

    - Lags: 1, 2, 3, 7, 14, 28
    - Rolling means: 7, 14, 30
    - Rolling means exclude the origin date.
    - Origin calendar features are included.

    The forecast-origin row must exist for every district.
    """

    weather_df = validate_weather_data(
        weather_df
    )

    forecast_origin = pd.Timestamp(
        forecast_origin
    ).normalize()

    # Only use observations available on or before origin
    weather_df = weather_df[
        weather_df["date"] <= forecast_origin
    ].copy()

    if weather_df.empty:
        raise ValueError(
            "No weather records available before "
            f"{forecast_origin.date()}."
        )

    # Check district coverage at the requested origin
    origin_records = weather_df[
        weather_df["date"] == forecast_origin
    ]

    if origin_records.empty:
        raise ValueError(
            "No weather records found for forecast origin "
            f"{forecast_origin.date()}."
        )

    all_districts = set(
        weather_df["district"].unique()
    )

    origin_districts = set(
        origin_records["district"].unique()
    )

    missing_districts = (
        all_districts - origin_districts
    )

    if missing_districts:
        raise ValueError(
            "Forecast-origin data missing for districts: "
            f"{sorted(missing_districts)}"
        )

    # --------------------------------------------------------
    # Create historical feature frame
    # --------------------------------------------------------

    feature_df = weather_df[
        ["district", "date"]
    ].copy()

    # Lag features
    for col in BASE_WEATHER_FEATURES:

        for lag in LAG_DAYS:

            feature_name = f"{col}_lag_{lag}"

            feature_df[feature_name] = (
                weather_df.groupby("district")[col]
                .shift(lag)
            )

    # Rolling means
    for col in ROLLING_VARIABLES:

        for window in ROLLING_WINDOWS:

            feature_name = (
                f"{col}_rolling_mean_{window}"
            )

            feature_df[feature_name] = (
                weather_df.groupby("district")[col]
                .transform(
                    lambda series: (
                        series.shift(1)
                        .rolling(
                            window=window,
                            min_periods=window
                        )
                        .mean()
                    )
                )
            )

    # Forecast-origin calendar features
    feature_df["origin_dayofyear_sin"] = np.sin(
        2 * np.pi
        * feature_df["date"].dt.dayofyear
        / 365.25
    )

    feature_df["origin_dayofyear_cos"] = np.cos(
        2 * np.pi
        * feature_df["date"].dt.dayofyear
        / 365.25
    )

    feature_df["origin_dayofweek"] = (
        feature_df["date"].dt.dayofweek
    )

    # Select requested forecast-origin records
    latest_features = feature_df[
        feature_df["date"] == forecast_origin
    ].copy()

    latest_features = latest_features.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Validate engineered features
    # --------------------------------------------------------

    engineered_columns = [
        col for col in feature_df.columns
        if col not in ["district", "date"]
    ]

    missing_values = (
        latest_features[engineered_columns]
        .isna()
        .sum()
    )

    problematic_features = missing_values[
        missing_values > 0
    ]

    if not problematic_features.empty:

        raise ValueError(
            "Missing values detected in engineered features. "
            "More historical data may be required.\n"
            f"{problematic_features.to_dict()}"
        )

    if not np.isfinite(
        latest_features[engineered_columns].to_numpy(
            dtype=float
        )
    ).all():

        raise ValueError(
            "Infinite values found in engineered features."
        )

    return latest_features


# ============================================================
# 7. PREPARE INPUTS FOR EACH TRAINED MODEL
# ============================================================

def prepare_model_inputs(
    latest_features,
    artifact
):
    """
    Prepare model inputs using the exact feature order
    stored in the trained model artifact.
    """

    model_df = latest_features.copy()

    horizon = int(
        artifact["horizon_days"]
    )

    # Calculate forecast target date
    model_df["target_date"] = (
        model_df["date"]
        + pd.to_timedelta(horizon, unit="D")
    )

    # Target-date calendar features
    model_df["target_dayofyear_sin"] = np.sin(
        2 * np.pi
        * model_df["target_date"].dt.dayofyear
        / 365.25
    )

    model_df["target_dayofyear_cos"] = np.cos(
        2 * np.pi
        * model_df["target_date"].dt.dayofyear
        / 365.25
    )

    model_df["target_month"] = (
        model_df["target_date"].dt.month
    )

    # Retrieve exact trained feature columns
    feature_columns = artifact["feature_columns"]

    missing_features = [
        col for col in feature_columns
        if col not in model_df.columns
    ]

    if missing_features:
        raise ValueError(
            "Required model features are missing: "
            f"{missing_features}"
        )

    X = model_df[feature_columns].copy()

    # Ensure numerical model inputs are numeric
    numerical_features = artifact[
        "numerical_features"
    ]

    for col in numerical_features:

        X[col] = pd.to_numeric(
            X[col],
            errors="coerce"
        )

    if X[numerical_features].isna().any().any():

        raise ValueError(
            "Missing numerical values found in model inputs."
        )

    if not np.isfinite(
        X[numerical_features].to_numpy(dtype=float)
    ).all():

        raise ValueError(
            "Infinite numerical values found in model inputs."
        )

    return X, model_df["target_date"]


# ============================================================
# 8. GENERATE FOUR MODEL PREDICTIONS
# ============================================================

def generate_weather_predictions(
    latest_features,
    models=None
):
    """
    Generate predictions using the four trained models.

    Outputs:
        Rainfall: 1-day and 7-day predictions
        Temperature: 1-day and 7-day predictions

    No model retraining is performed.
    """

    if models is None:
        models = load_weather_models()

    prediction_results = []

    for model_name, artifact in models.items():

        print(
            f"Generating predictions: {model_name}"
        )

        # Prepare model inputs
        X, target_dates = prepare_model_inputs(
            latest_features,
            artifact
        )

        # Apply original fitted preprocessing
        X_transformed = (
            artifact["preprocessor"].transform(X)
        )

        # Generate predictions
        predictions = artifact["model"].predict(
            X_transformed
        )

        # Validate prediction output
        if len(predictions) != len(latest_features):
            raise ValueError(
                f"Unexpected prediction count for {model_name}."
            )

        if not np.isfinite(predictions).all():
            raise ValueError(
                f"Non-finite predictions from {model_name}."
            )

        # Build result dataframe
        result = pd.DataFrame({
            "district": latest_features["district"].values,
            "forecast_origin": latest_features["date"].values,
            "forecast_date": target_dates.values,
            "target": artifact["target"],
            "horizon_days": artifact["horizon_days"],
            "model_name": artifact["model_name"],
            "predicted_value": predictions,
        })

        prediction_results.append(result)

    predictions_df = pd.concat(
        prediction_results,
        ignore_index=True
    )

    # Sort output
    predictions_df = predictions_df.sort_values(
        ["horizon_days", "target", "district"]
    ).reset_index(drop=True)

    return predictions_df


# ============================================================
# 9. SAVE OPERATIONAL PREDICTIONS
# ============================================================

def save_weather_predictions(
    predictions_df,
    output_path=OUTPUT_FILE
):
    """
    Save the latest ML predictions to CSV.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    predictions_df.to_csv(
        output_path,
        index=False
    )

    print("\nPredictions saved successfully.")
    print("Output file:", output_path)
    print("Total predictions:", len(predictions_df))

    return output_path


# ============================================================
# 10. RUN COMPLETE PREDICTION WORKFLOW
# ============================================================

def run_weather_prediction(
    weather_df,
    forecast_origin,
    save=True
):
    """
    Complete prediction workflow.

    Parameters
    ----------
    weather_df:
        Historical weather data combined with the latest
        completed daily weather records.

    forecast_origin:
        Date used as the model forecast origin.

    save:
        If True, save predictions to the operational CSV.

    Returns
    -------
    predictions_df:
        Predictions from all four trained models.
    """

    print("\n" + "=" * 65)
    print("RISKWEAVE AUTOMATIC WEATHER PREDICTION")
    print("=" * 65)

    print(
        "Forecast origin:",
        pd.Timestamp(forecast_origin).date()
    )

    # Load existing models
    models = load_weather_models()

    print(
        "\nLoaded trained models:",
        len(models)
    )

    # Create historical features
    latest_features = create_latest_weather_features(
        weather_df,
        forecast_origin
    )

    print(
        "Districts prepared:",
        latest_features["district"].nunique()
    )

    # Generate predictions
    predictions_df = generate_weather_predictions(
        latest_features,
        models
    )

    print("\nPrediction summary:")
    print(
        predictions_df.groupby(
            ["target", "horizon_days"]
        ).size()
    )

    # Save predictions
    if save:
        save_weather_predictions(
            predictions_df
        )

    print("\nWeather prediction workflow completed.")

    return predictions_df


# ============================================================
# 11. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    inspect_weather_models()

    print(
        "\nModel inspection completed successfully."
    )

    print(
        "To generate predictions, call "
        "run_weather_prediction() with the prepared "
        "historical and latest weather dataframe."
    )
