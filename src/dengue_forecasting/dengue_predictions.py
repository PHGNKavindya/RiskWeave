
from pathlib import Path

import joblib
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "forecasting"
    / "riskweave_daily_weather_experiment_model.joblib"
)

FEATURE_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "dengue_forecasting"
    / "latest_dengue_features.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "dengue_forecasting"

OUTPUT_FILE = OUTPUT_DIR / "next_week_dengue_predictions.csv"


def load_model():

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Trained model not found: {MODEL_FILE}"
        )

    return joblib.load(MODEL_FILE)


def load_features():

    if not FEATURE_FILE.exists():
        raise FileNotFoundError(
            f"Feature file not found: {FEATURE_FILE}"
        )

    features = pd.read_csv(FEATURE_FILE)

    if len(features) != 25:
        raise ValueError(
            f"Expected 25 districts, found {len(features)}"
        )

    return features


def predict_cases(model, features):

    # The district_key is also a model predictor.
    expected_features = list(model.feature_names_in_)

    missing_features = [
        col for col in expected_features
        if col not in features.columns
    ]

    if missing_features:
        raise ValueError(
            f"Missing model features: {missing_features}"
        )

    # Preserve the exact feature order used during training.
    X = features[expected_features].copy()

    if list(X.columns) != expected_features:
        raise ValueError("Model feature order mismatch.")

    predictions = model.predict(X)

    results = pd.DataFrame({
        "district_key": features["district_key"],
        "predicted_dengue_cases": predictions
    })

    # Dengue case counts cannot be negative.
    results["predicted_dengue_cases"] = (
        results["predicted_dengue_cases"]
        .clip(lower=0)
        .round()
        .astype(int)
    )

    return results


def main():

    print("\nRISKWEAVE DENGUE FORECASTING")
    print("============================")

    model = load_model()
    features = load_features()

    results = predict_cases(model, features)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results.to_csv(OUTPUT_FILE, index=False)

    print("\nPREDICTION COMPLETED")
    print("--------------------")
    print("Districts:", len(results))
    print("Output:", OUTPUT_FILE)

    print("\nDISTRICT PREDICTIONS")
    print(results.to_string(index=False))


if __name__ == "__main__":
    main()
