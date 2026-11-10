
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd
import joblib

# =====================================================
# RISKWEAVE - REUSABLE WEEKLY FORECASTING PIPELINE
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

DENGUE_FILE = ROOT / "data/processed/dengue_weekly_25_areas_2025_2026.csv"
WEATHER_FILE = ROOT / "data/processed/weather_operational_combined_2006_2026.csv"
MODEL_FILE = ROOT / "outputs/forecasting/riskweave_daily_weather_experiment_model.joblib"

OUTPUT_DIR = ROOT / "outputs/dengue_forecasting"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_FILE = OUTPUT_DIR / "latest_dengue_features.csv"
PREDICTION_FILE = OUTPUT_DIR / "latest_predictions.csv"
HISTORY_FILE = OUTPUT_DIR / "forecast_history.csv"

EXPECTED_DISTRICTS = 25

# -----------------------------------------------------
# 1. LOAD MODEL AND DATA
# -----------------------------------------------------

print("\nRISKWEAVE WEEKLY FORECASTING PIPELINE")
print("=" * 55)

for path in [DENGUE_FILE, WEATHER_FILE, MODEL_FILE]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

model = joblib.load(MODEL_FILE)
expected_features = list(model.feature_names_in_)

dengue = pd.read_csv(DENGUE_FILE)
weather = pd.read_csv(WEATHER_FILE)

# -----------------------------------------------------
# 2. PREPARE DENGUE WEEK IDENTIFIERS
# -----------------------------------------------------

dengue["year"] = dengue["year"].astype(int)
dengue["week"] = dengue["week"].astype(int)
dengue["weekly_cases"] = pd.to_numeric(
    dengue["weekly_cases"], errors="raise"
)

def week_monday(row):
    return pd.Timestamp.fromisocalendar(
        int(row["year"]), int(row["week"]), 1
    )

dengue["week_start"] = dengue.apply(week_monday, axis=1)

if dengue.duplicated(["district_key", "week_start"]).any():
    raise ValueError("Duplicate dengue district-week records.")

latest_start = dengue["week_start"].max()

latest_data = dengue[
    dengue["week_start"] == latest_start
]

if len(latest_data) != EXPECTED_DISTRICTS:
    raise ValueError(
        f"Latest dengue week has {len(latest_data)} records; "
        f"expected {EXPECTED_DISTRICTS}."
    )

iso = latest_start.isocalendar()
origin_year = int(iso.year)
origin_week = int(iso.week)

target_start = latest_start + pd.Timedelta(days=7)
target_iso = target_start.isocalendar()

target_year = int(target_iso.year)
target_week = int(target_iso.week)
target_end = target_start + pd.Timedelta(days=6)

print("Latest dengue week:", origin_year, origin_week)
print("Forecast target:", target_year, target_week)

# -----------------------------------------------------
# 3. PREPARE WEATHER DATA
# -----------------------------------------------------

weather["date"] = pd.to_datetime(weather["date"])

weather["district_key"] = (
    weather["district"]
    .astype(str)
    .str.strip()
    .str.lower()
    .replace({
        "monaragala": "moneragala",
        "nuwara eliya": "nuwaraeliya",
    })
)

weather["precipitation_sum"] = pd.to_numeric(
    weather["precipitation_sum"], errors="coerce"
)

weather = weather[
    (weather["date"] >= latest_start)
    & (weather["date"] <= latest_start + pd.Timedelta(days=6))
].copy()

if weather.duplicated(["district_key", "date"]).any():
    raise ValueError("Duplicate daily weather records found.")

weather_features = (
    weather.groupby("district_key")
    .agg(
        weather_days=("date", "nunique"),
        rainy_days=(
            "precipitation_sum",
            lambda x: (x > 0).sum()
        ),
        daily_rainfall_max=("precipitation_sum", "max"),
        daily_rainfall_std=("precipitation_sum", "std"),
    )
    .reset_index()
)

if len(weather_features) != EXPECTED_DISTRICTS:
    raise ValueError("Weather data does not cover all 25 areas.")

if (weather_features["weather_days"] != 7).any():
    raise ValueError("Some districts do not have seven weather days.")

if weather_features[
    ["daily_rainfall_max", "daily_rainfall_std"]
].isnull().any().any():
    raise ValueError("Missing rainfall values in weather features.")

weather_features["rainy_day_proportion"] = (
    weather_features["rainy_days"] / 7
)

# -----------------------------------------------------
# 4. GENERATE DENGUE LAG FEATURES
# -----------------------------------------------------

lookup = dengue.set_index(
    ["district_key", "week_start"]
)["weekly_cases"]

feature_rows = []

for _, current in latest_data.iterrows():

    district = current["district_key"]
    current_date = latest_start

    def get_cases(weeks_back):
        lookup_date = current_date - pd.Timedelta(
            weeks=weeks_back
        )
        key = (district, lookup_date)

        if key not in lookup.index:
            raise ValueError(
                f"Missing {weeks_back}-week historical lag "
                f"for {district}: {lookup_date.date()}"
            )

        return float(lookup.loc[key])

    lag_values = {
        f"dengue_lag_{i}": get_cases(i)
        for i in [1, 2, 3, 4, 51, 52]
    }

    rolling_values = [
        get_cases(i) for i in [0, 1, 2, 3]
    ]

    feature_rows.append({
        "district_key": district,
        "dengue_current_period": get_cases(0),
        **lag_values,
        "dengue_rolling_mean_4": np.mean(rolling_values),
        "month": current_date.month,
        "week_sin": np.sin(2 * np.pi * origin_week / 52),
        "week_cos": np.cos(2 * np.pi * origin_week / 52),
    })

dengue_features = pd.DataFrame(feature_rows)

# -----------------------------------------------------
# 5. MERGE WEATHER FEATURES
# -----------------------------------------------------

features = dengue_features.merge(
    weather_features[
        [
            "district_key",
            "rainy_day_proportion",
            "daily_rainfall_max",
            "daily_rainfall_std",
        ]
    ],
    on="district_key",
    how="left",
    validate="one_to_one"
)

# -----------------------------------------------------
# 6. VALIDATE MODEL INPUTS
# -----------------------------------------------------

if len(features) != EXPECTED_DISTRICTS:
    raise ValueError("Expected exactly 25 feature rows.")

if features["district_key"].nunique() != EXPECTED_DISTRICTS:
    raise ValueError("Duplicate or missing districts.")

missing = [
    col for col in expected_features
    if col not in features.columns
]

if missing:
    raise ValueError(f"Missing model columns: {missing}")

X = features[expected_features].copy()

if X.isnull().any().any():
    raise ValueError(
        "Missing model inputs:\n" + X.isnull().sum().to_string()
    )

# Save feature inputs for audit
features.to_csv(FEATURE_FILE, index=False)

# -----------------------------------------------------
# 7. GENERATE PREDICTIONS
# -----------------------------------------------------

predictions = model.predict(X)

results = pd.DataFrame({
    "district_key": features["district_key"],
    "forecast_origin_year": origin_year,
    "forecast_origin_week": origin_week,
    "target_year": target_year,
    "target_week": target_week,
    "target_week_start": target_start.date().isoformat(),
    "target_week_end": target_end.date().isoformat(),
    "predicted_dengue_cases": np.rint(
        np.maximum(predictions, 0)
    ).astype(int),
})

# -----------------------------------------------------
# 8. SAVE LATEST PREDICTIONS
# -----------------------------------------------------

results.to_csv(PREDICTION_FILE, index=False)

# -----------------------------------------------------
# 9. APPEND FORECAST HISTORY
# -----------------------------------------------------

if HISTORY_FILE.exists():
    history = pd.read_csv(HISTORY_FILE)

    history = history[
        ~(
            (history["target_year"] == target_year)
            & (history["target_week"] == target_week)
            & (history["district_key"].isin(results["district_key"]))
        )
    ]

    history = pd.concat(
        [history, results],
        ignore_index=True
    )
else:
    history = results.copy()

history.to_csv(HISTORY_FILE, index=False)

# -----------------------------------------------------
# 10. COMPLETION REPORT
# -----------------------------------------------------

print("\nFORECAST COMPLETED")
print("=" * 55)
print("Origin:", origin_year, "Week", origin_week)
print("Target:", target_year, "Week", target_week)
print("Districts:", len(results))
print("Model features:", len(expected_features))

print("\nSaved files:")
print(FEATURE_FILE)
print(PREDICTION_FILE)
print(HISTORY_FILE)

print("\nTOP 10 PREDICTED DISTRICTS:")
print(
    results.sort_values(
        "predicted_dengue_cases",
        ascending=False
    ).head(10).to_string(index=False)
)

print("\nRISKWEAVE PIPELINE FINISHED.")

