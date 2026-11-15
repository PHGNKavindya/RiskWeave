
from pathlib import Path

import pandas as pd


# ============================================================
# RISKWEAVE - ENVIRONMENTAL ANOMALY DETECTION
# ============================================================

# ------------------------------------------------------------
# 1. PROJECT PATHS
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_operational_combined_2006_2026.csv"
)

ANOMALY_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "environmental_anomalies"
)


# ------------------------------------------------------------
# 2. CONFIGURATION
# ------------------------------------------------------------

BASELINE_START_YEAR = 2007
BASELINE_END_YEAR = 2025
DETECTION_YEAR = 2026

EXPECTED_DISTRICTS = 25

REQUIRED_COLUMNS = [
    "district",
    "date",
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

WEATHER_VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

THRESHOLD_COLUMNS = [
    "rainfall_q01",
    "rainfall_q99",
    "temperature_q01",
    "temperature_q99",
    "humidity_q01",
    "humidity_q99"
]


# ============================================================
# 3. LOAD AND VALIDATE WEATHER DATA
# ============================================================

def load_weather_data():

    print("=" * 65)
    print("RISKWEAVE ENVIRONMENTAL ANOMALY DETECTION")
    print("=" * 65)

    print("\nLoading operational weather dataset...")

    if not WEATHER_FILE.exists():
        raise FileNotFoundError(
            f"Operational weather dataset not found: {WEATHER_FILE}"
        )

    weather_df = pd.read_csv(WEATHER_FILE)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in weather_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Required weather columns are missing: {missing_columns}"
        )

    weather_df = weather_df[REQUIRED_COLUMNS].copy()

    # Convert dates
    weather_df["date"] = pd.to_datetime(
        weather_df["date"],
        errors="coerce"
    )

    # Convert weather variables to numeric
    for column in WEATHER_VARIABLES:

        weather_df[column] = pd.to_numeric(
            weather_df[column],
            errors="coerce"
        )

    # Validate dates
    if weather_df["date"].isna().any():
        raise ValueError(
            "Weather dataset contains invalid or missing dates."
        )

    # Validate district names
    if weather_df["district"].isna().any():
        raise ValueError(
            "Weather dataset contains missing district names."
        )

    # Validate duplicates
    duplicate_count = weather_df.duplicated(
        subset=["district", "date"]
    ).sum()

    if duplicate_count > 0:
        raise ValueError(
            f"Found {duplicate_count} duplicate district-date records."
        )

    # Validate missing weather values
    missing_values = (
        weather_df[WEATHER_VARIABLES]
        .isna()
        .sum()
    )

    print("\nMISSING WEATHER VALUES")
    print("-" * 65)
    print(missing_values)

    if missing_values.sum() > 0:
        raise ValueError(
            "Missing values detected in selected weather variables. "
            "Resolve data quality issues before anomaly detection."
        )

    # Validate district coverage
    district_count = weather_df["district"].nunique()

    if district_count != EXPECTED_DISTRICTS:
        raise ValueError(
            f"Expected {EXPECTED_DISTRICTS} districts, "
            f"but found {district_count}."
        )

    return weather_df


# ============================================================
# 4. INSPECT WEATHER DATA
# ============================================================

def inspect_weather_data(weather_df):

    print("\n" + "=" * 65)
    print("DATASET INFORMATION")
    print("=" * 65)

    print("Total records:", f"{len(weather_df):,}")

    print(
        "Districts:",
        weather_df["district"].nunique()
    )

    print(
        "Start date:",
        weather_df["date"].min()
    )

    print(
        "End date:",
        weather_df["date"].max()
    )

    print("\nDUPLICATE RECORD CHECK")
    print("-" * 65)

    duplicate_count = weather_df.duplicated(
        subset=["district", "date"]
    ).sum()

    print("Duplicate records:", duplicate_count)

    print("\nMISSING WEATHER VALUES")
    print("-" * 65)

    print(
        weather_df[WEATHER_VARIABLES]
        .isna()
        .sum()
    )

    print("\nDATA VALIDATION COMPLETED.")


# ============================================================
# 5. CALCULATE HISTORICAL SEASONAL BASELINE
# ============================================================

def calculate_historical_baseline(weather_df):

    print("\n" + "=" * 65)
    print("STEP 3: HISTORICAL SEASONAL BASELINE")
    print("=" * 65)

    # --------------------------------------------------------
    # 5.1 Prepare baseline dataset
    # --------------------------------------------------------

    baseline_df = weather_df.copy()

    baseline_df["year"] = (
        baseline_df["date"].dt.year
    )

    baseline_df["month"] = (
        baseline_df["date"].dt.month
    )

    baseline_history = baseline_df[
        baseline_df["year"].between(
            BASELINE_START_YEAR,
            BASELINE_END_YEAR
        )
    ].copy()

    print("\nBASELINE PERIOD")
    print("-" * 65)

    print("Start year:", BASELINE_START_YEAR)
    print("End year:", BASELINE_END_YEAR)

    print(
        "Historical records:",
        f"{len(baseline_history):,}"
    )

    print(
        "Districts:",
        baseline_history["district"].nunique()
    )

    if baseline_history.empty:
        raise ValueError(
            "No historical observations found for baseline calculation."
        )

    # --------------------------------------------------------
    # 5.2 Calculate district-month percentile thresholds
    # --------------------------------------------------------

    baseline_thresholds = (
        baseline_history
        .groupby(["district", "month"])
        .agg(
            rainfall_q01=(
                "precipitation_sum",
                lambda x: x.quantile(0.01)
            ),

            rainfall_q99=(
                "precipitation_sum",
                lambda x: x.quantile(0.99)
            ),

            temperature_q01=(
                "temperature_2m_mean",
                lambda x: x.quantile(0.01)
            ),

            temperature_q99=(
                "temperature_2m_mean",
                lambda x: x.quantile(0.99)
            ),

            humidity_q01=(
                "relative_humidity_2m_mean",
                lambda x: x.quantile(0.01)
            ),

            humidity_q99=(
                "relative_humidity_2m_mean",
                lambda x: x.quantile(0.99)
            ),

            baseline_observations=("date", "count")
        )
        .reset_index()
    )

    print("\nBASELINE THRESHOLD SUMMARY")
    print("-" * 65)

    print(
        "District-month groups:",
        len(baseline_thresholds)
    )

    print(
        "Expected groups:",
        EXPECTED_DISTRICTS * 12
    )

    print("\nObservations per group:")

    print(
        baseline_thresholds[
            "baseline_observations"
        ].describe()
    )

    # --------------------------------------------------------
    # 5.3 Validate thresholds
    # --------------------------------------------------------

    print("\nTHRESHOLD VALIDATION")
    print("-" * 65)

    missing_thresholds = (
        baseline_thresholds[THRESHOLD_COLUMNS]
        .isna()
        .sum()
        .sum()
    )

    print(
        "Missing threshold values:",
        missing_thresholds
    )

    invalid_rainfall = (
        baseline_thresholds["rainfall_q01"]
        > baseline_thresholds["rainfall_q99"]
    ).sum()

    invalid_temperature = (
        baseline_thresholds["temperature_q01"]
        > baseline_thresholds["temperature_q99"]
    ).sum()

    invalid_humidity = (
        baseline_thresholds["humidity_q01"]
        > baseline_thresholds["humidity_q99"]
    ).sum()

    print(
        "Invalid rainfall ordering:",
        invalid_rainfall
    )

    print(
        "Invalid temperature ordering:",
        invalid_temperature
    )

    print(
        "Invalid humidity ordering:",
        invalid_humidity
    )

    if missing_thresholds > 0:
        raise ValueError(
            "Historical baseline contains missing thresholds."
        )

    if (
        invalid_rainfall > 0
        or invalid_temperature > 0
        or invalid_humidity > 0
    ):
        raise ValueError(
            "Historical baseline contains invalid percentile ordering."
        )

    expected_groups = EXPECTED_DISTRICTS * 12

    if len(baseline_thresholds) != expected_groups:
        raise ValueError(
            f"Expected {expected_groups} district-month groups, "
            f"but found {len(baseline_thresholds)}."
        )

    # --------------------------------------------------------
    # 5.4 Display sample thresholds
    # --------------------------------------------------------

    print("\nSAMPLE DISTRICT THRESHOLDS")
    print("-" * 65)

    sample_districts = [
        "Colombo",
        "Kandy",
        "Jaffna",
        "Nuwara Eliya",
        "Galle"
    ]

    sample_thresholds = baseline_thresholds[
        baseline_thresholds["district"].isin(
            sample_districts
        )
    ]

    sample_columns = [
        "district",
        "month",
        "rainfall_q99",
        "temperature_q01",
        "temperature_q99",
        "humidity_q01",
        "humidity_q99",
        "baseline_observations"
    ]

    print(
        sample_thresholds[
            sample_columns
        ].to_string(index=False)
    )

    # --------------------------------------------------------
    # 5.5 Save historical baseline
    # --------------------------------------------------------

    ANOMALY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    baseline_file = (
        ANOMALY_DIR
        / "district_monthly_weather_baselines.csv"
    )

    baseline_thresholds.to_csv(
        baseline_file,
        index=False
    )

    print("\nBASELINE FILE SAVED")
    print("-" * 65)

    print(baseline_file)

    print("\nSTEP 3 COMPLETED.")

    return baseline_thresholds


# ============================================================
# 6. DETECT ENVIRONMENTAL ANOMALIES
# ============================================================

def detect_environmental_anomalies(
    weather_df,
    baseline_thresholds
):

    print("\n" + "=" * 65)
    print("STEP 4: DETECTING WEATHER ANOMALIES")
    print("=" * 65)

    # --------------------------------------------------------
    # 6.1 Prepare detection dataset
    # --------------------------------------------------------

    detection_df = weather_df.copy()

    detection_df["year"] = (
        detection_df["date"].dt.year
    )

    detection_df["month"] = (
        detection_df["date"].dt.month
    )

    detection_df = detection_df[
        detection_df["year"] == DETECTION_YEAR
    ].copy()

    if detection_df.empty:
        raise ValueError(
            f"No observations found for detection year {DETECTION_YEAR}."
        )

    print("\nDETECTION DATA")
    print("-" * 65)

    print("Records:", len(detection_df))

    print(
        "Districts:",
        detection_df["district"].nunique()
    )

    print(
        "Start date:",
        detection_df["date"].min()
    )

    print(
        "End date:",
        detection_df["date"].max()
    )

    # --------------------------------------------------------
    # 6.2 Merge historical thresholds
    # --------------------------------------------------------

    detection_df = detection_df.merge(
        baseline_thresholds,
        on=["district", "month"],
        how="left",
        validate="many_to_one"
    )

    if detection_df[THRESHOLD_COLUMNS].isna().any().any():
        raise ValueError(
            "Some detection observations do not have "
            "historical district-month thresholds."
        )

    # --------------------------------------------------------
    # 6.3 Rainfall anomalies
    # --------------------------------------------------------

    detection_df["rainfall_anomaly"] = (
        detection_df["precipitation_sum"]
        > detection_df["rainfall_q99"]
    )

    detection_df["rainfall_anomaly_type"] = ""

    detection_df.loc[
        detection_df["rainfall_anomaly"],
        "rainfall_anomaly_type"
    ] = "Unusually high rainfall"

    # --------------------------------------------------------
    # 6.4 Temperature anomalies
    # --------------------------------------------------------

    detection_df["temperature_low_anomaly"] = (
        detection_df["temperature_2m_mean"]
        < detection_df["temperature_q01"]
    )

    detection_df["temperature_high_anomaly"] = (
        detection_df["temperature_2m_mean"]
        > detection_df["temperature_q99"]
    )

    detection_df["temperature_anomaly"] = (
        detection_df["temperature_low_anomaly"]
        | detection_df["temperature_high_anomaly"]
    )

    detection_df["temperature_anomaly_type"] = ""

    detection_df.loc[
        detection_df["temperature_low_anomaly"],
        "temperature_anomaly_type"
    ] = "Unusually low temperature"

    detection_df.loc[
        detection_df["temperature_high_anomaly"],
        "temperature_anomaly_type"
    ] = "Unusually high temperature"

    # --------------------------------------------------------
    # 6.5 Relative humidity anomalies
    # --------------------------------------------------------

    detection_df["humidity_low_anomaly"] = (
        detection_df["relative_humidity_2m_mean"]
        < detection_df["humidity_q01"]
    )

    detection_df["humidity_high_anomaly"] = (
        detection_df["relative_humidity_2m_mean"]
        > detection_df["humidity_q99"]
    )

    detection_df["humidity_anomaly"] = (
        detection_df["humidity_low_anomaly"]
        | detection_df["humidity_high_anomaly"]
    )

    detection_df["humidity_anomaly_type"] = ""

    detection_df.loc[
        detection_df["humidity_low_anomaly"],
        "humidity_anomaly_type"
    ] = "Unusually low humidity"

    detection_df.loc[
        detection_df["humidity_high_anomaly"],
        "humidity_anomaly_type"
    ] = "Unusually high humidity"

    # --------------------------------------------------------
    # 6.6 Calculate anomaly counts
    # --------------------------------------------------------

    anomaly_flag_columns = [
        "rainfall_anomaly",
        "temperature_anomaly",
        "humidity_anomaly"
    ]

    detection_df["anomaly_count"] = (
        detection_df[anomaly_flag_columns]
        .sum(axis=1)
    )

    detection_df["any_anomaly"] = (
        detection_df["anomaly_count"] > 0
    )

    # Descriptive classification only.
    # This is NOT a dengue-risk classification.

    detection_df["anomaly_category"] = (
        "No detected anomaly"
    )

    detection_df.loc[
        detection_df["anomaly_count"] == 1,
        "anomaly_category"
    ] = "Single-variable anomaly"

    detection_df.loc[
        detection_df["anomaly_count"] == 2,
        "anomaly_category"
    ] = "Two-variable anomaly"

    detection_df.loc[
        detection_df["anomaly_count"] == 3,
        "anomaly_category"
    ] = "Multi-variable anomaly"

    # --------------------------------------------------------
    # 6.7 Overall anomaly summary
    # --------------------------------------------------------

    print("\nOVERALL ANOMALY SUMMARY")
    print("-" * 65)

    for column, label in [
        ("rainfall_anomaly", "Rainfall anomalies"),
        ("temperature_anomaly", "Temperature anomalies"),
        ("humidity_anomaly", "Humidity anomalies"),
        ("any_anomaly", "District-days with at least one anomaly")
    ]:

        count = int(detection_df[column].sum())

        percentage = (
            count / len(detection_df) * 100
        )

        print(
            f"{label}: {count:,} ({percentage:.2f}%)"
        )

    print("\nANOMALY CATEGORY COUNTS")
    print("-" * 65)

    print(
        detection_df["anomaly_category"]
        .value_counts()
        .to_string()
    )

    # --------------------------------------------------------
    # 6.8 District-level summary
    # --------------------------------------------------------

    print("\nDISTRICT-LEVEL ANOMALY SUMMARY")
    print("-" * 65)

    district_summary = (
        detection_df
        .groupby("district")
        .agg(
            total_days=("date", "count"),

            rainfall_anomalies=(
                "rainfall_anomaly",
                "sum"
            ),

            temperature_anomalies=(
                "temperature_anomaly",
                "sum"
            ),

            humidity_anomalies=(
                "humidity_anomaly",
                "sum"
            ),

            days_with_anomalies=(
                "any_anomaly",
                "sum"
            )
        )
        .reset_index()
    )

    district_summary["anomaly_percentage"] = (
        district_summary["days_with_anomalies"]
        / district_summary["total_days"]
        * 100
    )

    district_summary = (
        district_summary
        .sort_values(
            "days_with_anomalies",
            ascending=False
        )
    )

    print(
        district_summary.to_string(index=False)
    )

    # --------------------------------------------------------
    # 6.9 Save daily and district outputs
    # --------------------------------------------------------

    ANOMALY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    daily_output_file = (
        ANOMALY_DIR
        / "weather_anomaly_daily_2026.csv"
    )

    district_output_file = (
        ANOMALY_DIR
        / "district_anomaly_summary_2026.csv"
    )

    detection_df.to_csv(
        daily_output_file,
        index=False
    )

    district_summary.to_csv(
        district_output_file,
        index=False
    )

    print("\nANOMALY OUTPUT FILES SAVED")
    print("-" * 65)

    print(daily_output_file)
    print(district_output_file)

    print("\nSTEP 4 COMPLETED.")

    return detection_df, district_summary


# ============================================================
# 7. MONTHLY ANOMALY SUMMARY
# ============================================================

def create_monthly_anomaly_summary(detection_df):

    print("\n" + "=" * 65)
    print("STEP 5: MONTHLY ANOMALY SUMMARY")
    print("=" * 65)

    # --------------------------------------------------------
    # 7.1 Calculate monthly anomaly summary
    # --------------------------------------------------------

    monthly_summary = (
        detection_df
        .groupby("month")
        .agg(
            total_observations=("date", "count"),

            rainfall_anomalies=(
                "rainfall_anomaly",
                "sum"
            ),

            temperature_anomalies=(
                "temperature_anomaly",
                "sum"
            ),

            humidity_anomalies=(
                "humidity_anomaly",
                "sum"
            ),

            days_with_anomalies=(
                "any_anomaly",
                "sum"
            )
        )
        .reset_index()
    )

    monthly_summary["anomaly_percentage"] = (
        monthly_summary["days_with_anomalies"]
        / monthly_summary["total_observations"]
        * 100
    )

    month_names = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December"
    }

    monthly_summary["month_name"] = (
        monthly_summary["month"].map(month_names)
    )

    print("\nMONTHLY ANOMALY SUMMARY")
    print("-" * 65)

    display_columns = [
        "month_name",
        "total_observations",
        "rainfall_anomalies",
        "temperature_anomalies",
        "humidity_anomalies",
        "days_with_anomalies",
        "anomaly_percentage"
    ]

    print(
        monthly_summary[
            display_columns
        ].to_string(index=False)
    )

    # --------------------------------------------------------
    # 7.2 Save monthly summary
    # --------------------------------------------------------

    monthly_output_file = (
        ANOMALY_DIR
        / "monthly_anomaly_summary_2026.csv"
    )

    monthly_summary.to_csv(
        monthly_output_file,
        index=False
    )

    print("\nMONTHLY SUMMARY SAVED")
    print("-" * 65)

    print(monthly_output_file)

    print("\nSTEP 5 COMPLETED.")

    return monthly_summary


# ============================================================
# 8. MAIN ANOMALY DETECTION PIPELINE
# ============================================================

def run_anomaly_detection():

    # Step 1: Load and validate operational weather
    weather_df = load_weather_data()

    # Step 2: Inspect weather data
    inspect_weather_data(weather_df)

    # Step 3: Calculate historical seasonal baseline
    baseline_thresholds = calculate_historical_baseline(
        weather_df
    )

    # Step 4: Detect environmental anomalies
    detection_df, district_summary = (
        detect_environmental_anomalies(
            weather_df,
            baseline_thresholds
        )
    )

    # Step 5: Create monthly anomaly summary
    monthly_summary = create_monthly_anomaly_summary(
        detection_df
    )

    print("\n" + "=" * 65)
    print("ENVIRONMENTAL ANOMALY DETECTION COMPLETED")
    print("=" * 65)

    print("\nGenerated files:")

    print(
        ANOMALY_DIR
        / "district_monthly_weather_baselines.csv"
    )

    print(
        ANOMALY_DIR
        / "weather_anomaly_daily_2026.csv"
    )

    print(
        ANOMALY_DIR
        / "district_anomaly_summary_2026.csv"
    )

    print(
        ANOMALY_DIR
        / "monthly_anomaly_summary_2026.csv"
    )

    return (
        baseline_thresholds,
        detection_df,
        district_summary,
        monthly_summary
    )


# ============================================================
# 9. SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_anomaly_detection()
