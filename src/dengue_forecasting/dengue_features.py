
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DENGUE_FILE = (
    PROJECT_ROOT / "data" / "processed"
    / "dengue_weekly_25_districts.csv"
)

WEATHER_FEATURE_FILE = (
    PROJECT_ROOT / "data" / "processed"
    / "daily_derived_weather_period_features.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "dengue_forecasting"

FEATURE_COLUMNS = [
    "district_key",
    "dengue_current_period",
    "dengue_lag_1",
    "dengue_lag_2",
    "dengue_lag_3",
    "dengue_lag_4",
    "dengue_lag_51",
    "dengue_lag_52",
    "dengue_rolling_mean_4",
    "month",
    "week_sin",
    "week_cos",
    "rainy_day_proportion",
    "daily_rainfall_max",
    "daily_rainfall_std",
]


def load_data():

    if not DENGUE_FILE.exists():
        raise FileNotFoundError(DENGUE_FILE)

    if not WEATHER_FEATURE_FILE.exists():
        raise FileNotFoundError(WEATHER_FEATURE_FILE)

    dengue = pd.read_csv(DENGUE_FILE)
    weather = pd.read_csv(WEATHER_FEATURE_FILE)

    dengue["week_start"] = pd.to_datetime(dengue["week_start"])
    weather["week_start"] = pd.to_datetime(weather["week_start"])

    if "week_end" in dengue.columns:
        dengue["week_end"] = pd.to_datetime(dengue["week_end"])

    return dengue, weather


def create_dengue_features(dengue):

    dengue = dengue.sort_values(
        ["district_key", "week_start"]
    ).copy()

    grouped = dengue.groupby("district_key", sort=False)["dengue_cases"]

    dengue["dengue_current_period"] = dengue["dengue_cases"]

    for lag in [1, 2, 3, 4, 51, 52]:
        dengue[f"dengue_lag_{lag}"] = grouped.shift(lag)

    dengue["dengue_rolling_mean_4"] = (
        dengue.groupby("district_key", sort=False)["dengue_cases"]
        .transform(
            lambda s: s.rolling(window=4, min_periods=2).mean()
        )
    )

    week_number = (
        dengue["week_start"].dt.isocalendar().week.astype(int)
    )

    dengue["month"] = dengue["week_start"].dt.month

    dengue["week_sin"] = np.sin(
        2 * np.pi * week_number / 52.1775
    )

    dengue["week_cos"] = np.cos(
        2 * np.pi * week_number / 52.1775
    )

    return dengue


def prepare_latest_features(dengue, weather):

    required_weather = [
        "district_key",
        "week_start",
        "rainy_day_proportion",
        "daily_rainfall_max",
        "daily_rainfall_std",
    ]

    missing = set(required_weather) - set(weather.columns)

    if missing:
        raise ValueError(
            f"Weather feature dataset is missing: {sorted(missing)}"
        )

    dengue = create_dengue_features(dengue)

    latest_date = dengue["week_start"].max()

    latest_dengue = dengue[
        dengue["week_start"] == latest_date
    ].copy()

    latest_weather = weather[
        weather["week_start"] == latest_date
    ][required_weather].copy()

    features = latest_dengue.merge(
        latest_weather,
        on=["district_key", "week_start"],
        how="left",
        validate="one_to_one"
    )

    missing_features = features[FEATURE_COLUMNS].isna().sum()

    if missing_features.any():
        raise ValueError(
            "Missing model features:\n"
            + missing_features[missing_features > 0].to_string()
        )

    features = features[FEATURE_COLUMNS].copy()

    return features, latest_date


def main():

    dengue, weather = load_data()

    features, latest_date = prepare_latest_features(
        dengue, weather
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "latest_dengue_features.csv"

    features.to_csv(output_file, index=False)

    print("\nDENGUE FEATURE PREPARATION")
    print("--------------------------")
    print("Latest dengue period:", latest_date.date())
    print("Districts prepared:", len(features))
    print("Model features:", len(FEATURE_COLUMNS))
    print("Saved:", output_file)

    print("\nIMPORTANT:")
    print(
        "These features represent the latest historical dengue "
        "reporting period. They are not automatically a current "
        "November 2026 forecast input."
    )


if __name__ == "__main__":
    main()
