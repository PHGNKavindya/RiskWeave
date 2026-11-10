
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DENGUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dengue_weekly_25_districts.csv"
)

WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather_live"
    / "yesterday_completed_weather.csv"
)

MODEL_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "forecasting"
    / "riskweave_daily_weather_experiment_model.joblib"
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


def load_dengue_data():
    """Load historical weekly dengue counts."""

    if not DENGUE_FILE.exists():
        raise FileNotFoundError(
            f"Dengue dataset not found: {DENGUE_FILE}"
        )

    dengue = pd.read_csv(DENGUE_FILE)

    required = {
        "district_key",
        "week_start",
        "dengue_cases",
    }

    missing = required - set(dengue.columns)

    if missing:
        raise ValueError(
            f"Dengue dataset is missing columns: {sorted(missing)}"
        )

    dengue["week_start"] = pd.to_datetime(
        dengue["week_start"], errors="coerce"
    )

    dengue["dengue_cases"] = pd.to_numeric(
        dengue["dengue_cases"], errors="coerce"
    )

    dengue = dengue.dropna(
        subset=["district_key", "week_start", "dengue_cases"]
    )

    dengue = dengue.sort_values(
        ["district_key", "week_start"]
    ).reset_index(drop=True)

    return dengue


def load_weather_data():
    """Load the existing completed daily weather data."""

    if not WEATHER_FILE.exists():
        raise FileNotFoundError(
            f"Weather data not found: {WEATHER_FILE}"
        )

    weather = pd.read_csv(WEATHER_FILE)

    required = {
        "district",
        "date",
        "precipitation_sum",
    }

    missing = required - set(weather.columns)

    if missing:
        raise ValueError(
            f"Weather dataset is missing columns: {sorted(missing)}"
        )

    weather["date"] = pd.to_datetime(
        weather["date"], errors="coerce"
    )

    weather["precipitation_sum"] = pd.to_numeric(
        weather["precipitation_sum"], errors="coerce"
    )

    weather = weather.dropna(
        subset=["district", "date", "precipitation_sum"]
    )

    return weather


def build_dengue_features(dengue, weather):
    """
    Build one prediction row per district.

    Weather is aggregated over the latest completed dengue
    reporting period. This preserves the timing used by the
    daily-weather model.
    """

    latest_date = dengue["week_start"].max()

    latest_period = dengue[
        dengue["week_start"] == latest_date
    ].copy()

    # Do not combine current weather with old dengue observations.
    weather_latest = weather["date"].max()

    weather_latest_day = weather[
        weather["date"] == weather_latest
    ]

    print(f"Latest dengue period start: {latest_date.date()}")
    print(f"Latest available weather date: {weather_latest.date()}")

    # Use the latest dengue reporting period's actual dates.
    latest_rows = dengue[
        dengue["week_start"] == latest_date
    ]

    if "week_end" in latest_rows.columns:
        latest_end = pd.to_datetime(
            latest_rows["week_end"]
        ).max()
    else:
        latest_end = latest_date + pd.Timedelta(days=6)

    weather_period = weather[
        (weather["date"] >= latest_date)
        & (weather["date"] <= latest_end)
    ].copy()

    if weather_period.empty:
        raise ValueError(
            "No daily weather records match the latest dengue "
            "reporting period. Update the dengue data or weather "
            "history before forecasting."
        )

    weather_features = (
        weather_period.groupby("district")
        .agg(
            rainy_day_proportion=(
                "precipitation_sum",
                lambda x: (x > 0).sum() / len(x)
            ),
            daily_rainfall_max=(
                "precipitation_sum", "max"
            ),
            daily_rainfall_std=(
                "precipitation_sum", "std"
            ),
        )
        .reset_index()
    )

    weather_features = weather_features.rename(
        columns={"district": "district_key"}
    )

    weather_features["daily_rainfall_std"] = (
        weather_features["daily_rainfall_std"].fillna(0)
    )

    rows = []

    for district in sorted(dengue["district_key"].unique()):

        district_data = (
            dengue[dengue["district_key"] == district]
            .sort_values("week_start")
            .reset_index(drop=True)
        )

        current = district_data[
            district_data["week_start"] == latest_date
        ]

        if current.empty:
            continue

        # Use one observation for each reporting period.
        current_index = current.index[-1]

        if current_index < 52:
            continue

        cases = district_data["dengue_cases"]

        row = {
            "district_key": district,
            "dengue_current_period": cases.iloc[current_index],
            "dengue_lag_1": cases.iloc[current_index - 1],
            "dengue_lag_2": cases.iloc[current_index - 2],
            "dengue_lag_3": cases.iloc[current_index - 3],
            "dengue_lag_4": cases.iloc[current_index - 4],
            "dengue_lag_51": cases.iloc[current_index - 51],
            "dengue_lag_52": cases.iloc[current_index - 52],
            "dengue_rolling_mean_4": (
                cases.iloc[current_index - 3:current_index + 1].mean()
            ),
            "month": latest_date.month,
            "week_sin": np.sin(
                2 * np.pi * latest_date.isocalendar().week / 52
            ),
            "week_cos": np.cos(
                2 * np.pi * latest_date.isocalendar().week / 52
            ),
        }

        rows.append(row)

    features = pd.DataFrame(rows)

    features = features.merge(
        weather_features,
        on="district_key",
        how="left"
    )

    if features.empty:
        raise ValueError(
            "No districts have enough historical dengue records "
            "to construct all model lag features."
        )

    missing_weather = features[
        [
            "rainy_day_proportion",
            "daily_rainfall_max",
            "daily_rainfall_std",
        ]
    ].isna().any(axis=1)

    if missing_weather.any():
        missing_districts = features.loc[
            missing_weather, "district_key"
        ].tolist()

        raise ValueError(
            "Weather features are missing for districts: "
            f"{missing_districts}"
        )

    return features[FEATURE_COLUMNS]


def main():
    dengue = load_dengue_data()
    weather = load_weather_data()

    latest_dengue_date = dengue["week_start"].max()
    age_days = (pd.Timestamp.today().normalize() - latest_dengue_date).days

    print("\nDENGUE DATA CHECK")
    print("-----------------")
    print("Latest dengue period:", latest_dengue_date.date())
    print("Days since period start:", age_days)

    if age_days > 14:
        raise ValueError(
            "Dengue observations are too old for a current next-week "
            "forecast. Update the weekly dengue case dataset first. "
            f"Latest available period: {latest_dengue_date.date()}"
        )

    features = build_dengue_features(dengue, weather)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = OUTPUT_DIR / "latest_dengue_features.csv"
    features.to_csv(output_file, index=False)

    print("\nFeature preparation completed.")
    print("Districts prepared:", len(features))
    print("Features prepared:", len(FEATURE_COLUMNS))
    print("Saved:", output_file)


if __name__ == "__main__":
    main()
