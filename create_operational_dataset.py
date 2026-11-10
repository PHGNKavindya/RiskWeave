
from pathlib import Path
import pandas as pd


# ============================================================
# RISKWEAVE - CREATE OPERATIONAL WEATHER DATASET
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

ERA5_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_era5_combined_2006_2026.csv"
)

HISTORICAL_API_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather_live"
    / "recent_historical_weather.csv"
)

FORECAST_API_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather_live"
    / "yesterday_completed_weather.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_operational_combined_2006_2026.csv"
)

EXPECTED_DISTRICTS = 25

REQUIRED_FEATURES = [
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
# 1. LOAD AND VALIDATE WEATHER FILE
# ============================================================

def load_weather_file(file_path, source_name):

    if not file_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {file_path}"
        )

    df = pd.read_csv(file_path)

    required_columns = [
        "district",
        "date"
    ] + REQUIRED_FEATURES

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"{source_name} is missing columns: "
            f"{missing_columns}"
        )

    df["district"] = (
        df["district"]
        .astype("string")
        .str.strip()
    )

    if df["district"].isna().any() or (
        df["district"] == ""
    ).any():
        raise ValueError(
            f"{source_name} contains missing district names."
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    ).dt.normalize()

    if df["date"].isna().any():
        raise ValueError(
            f"{source_name} contains invalid dates."
        )

    if df.duplicated(
        subset=["district", "date"]
    ).any():
        raise ValueError(
            f"{source_name} contains duplicate district-date records."
        )

    for col in REQUIRED_FEATURES:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    missing_values = (
        df[REQUIRED_FEATURES]
        .isna()
        .sum()
    )

    missing_values = missing_values[
        missing_values > 0
    ]

    if not missing_values.empty:

        raise ValueError(
            f"{source_name} contains missing required features:\n"
            f"{missing_values}"
        )

    # Assign source label explicitly.
    df["data_source"] = source_name

    return df


# ============================================================
# 2. CREATE OPERATIONAL DATASET
# ============================================================

def create_operational_dataset():

    print("\n" + "=" * 65)
    print("RISKWEAVE OPERATIONAL DATASET CREATION")
    print("=" * 65)

    # --------------------------------------------------------
    # Load ERA5 data
    # --------------------------------------------------------

    print("\nLoading ERA5 dataset...")

    era5_df = load_weather_file(
        ERA5_FILE,
        "ERA5"
    )

    print("ERA5 records:", len(era5_df))

    # --------------------------------------------------------
    # Load historical API data
    # --------------------------------------------------------

    print("\nLoading recent historical API dataset...")

    historical_api_df = load_weather_file(
        HISTORICAL_API_FILE,
        "Open-Meteo Historical Weather API"
    )

    print(
        "Historical API records:",
        len(historical_api_df)
    )

    # --------------------------------------------------------
    # Load yesterday's completed API observations
    # --------------------------------------------------------

    print("\nLoading yesterday's forecast API dataset...")

    forecast_api_df = load_weather_file(
        FORECAST_API_FILE,
        "Open-Meteo Forecast API"
    )

    print(
        "Forecast API records:",
        len(forecast_api_df)
    )

    # ========================================================
    # 3. VALIDATE DISTRICT CONSISTENCY
    # ========================================================

    era5_districts = set(
        era5_df["district"].unique()
    )

    historical_districts = set(
        historical_api_df["district"].unique()
    )

    forecast_districts = set(
        forecast_api_df["district"].unique()
    )

    if len(era5_districts) != EXPECTED_DISTRICTS:

        raise ValueError(
            "ERA5 does not contain exactly 25 districts."
        )

    if (
        era5_districts != historical_districts
        or era5_districts != forecast_districts
    ):

        raise ValueError(
            "District names differ between the three datasets."
        )

    print("\nDistrict consistency: PASSED")

    # ========================================================
    # 4. VALIDATE DATE SEQUENCE BETWEEN SOURCES
    # ========================================================

    era5_latest = era5_df["date"].max()

    historical_start = historical_api_df["date"].min()
    historical_end = historical_api_df["date"].max()

    forecast_date = forecast_api_df["date"].min()

    if historical_start != (
        era5_latest + pd.Timedelta(days=1)
    ):

        raise ValueError(
            "Historical API does not start immediately "
            "after the ERA5 dataset."
        )

    if historical_end + pd.Timedelta(days=1) != forecast_date:

        raise ValueError(
            "Forecast API completed data does not immediately "
            "follow the historical API data."
        )

    print("ERA5 to Historical API continuity: PASSED")
    print("Historical API to Forecast API continuity: PASSED")

    # ========================================================
    # 5. COMBINE DATASETS
    # ========================================================

    print("\nCombining weather datasets...")

    combined_df = pd.concat(
        [
            era5_df,
            historical_api_df,
            forecast_api_df
        ],
        ignore_index=True,
        sort=False
    )

    combined_df["date"] = pd.to_datetime(
        combined_df["date"]
    ).dt.normalize()

    combined_df = (
        combined_df
        .sort_values(["district", "date"])
        .reset_index(drop=True)
    )

    # ========================================================
    # 6. CHECK DUPLICATE DISTRICT-DATE RECORDS
    # ========================================================

    duplicate_count = combined_df.duplicated(
        subset=["district", "date"]
    ).sum()

    if duplicate_count > 0:

        raise ValueError(
            f"Combined dataset contains {duplicate_count} "
            "duplicate district-date records."
        )

    print("Duplicate validation: PASSED")

    # ========================================================
    # 7. CHECK DAILY CONTINUITY
    # ========================================================

    expected_start = era5_df["date"].min()

    expected_end = max(
        era5_df["date"].max(),
        historical_api_df["date"].max(),
        forecast_api_df["date"].max()
    )

    expected_dates = pd.date_range(
        start=expected_start,
        end=expected_end,
        freq="D"
    )

    for district, group in combined_df.groupby("district"):

        actual_dates = pd.DatetimeIndex(
            group["date"].sort_values().unique()
        )

        missing_dates = expected_dates.difference(
            actual_dates
        )

        unexpected_dates = actual_dates.difference(
            expected_dates
        )

        if (
            len(missing_dates) > 0
            or len(unexpected_dates) > 0
        ):

            raise ValueError(
                f"Daily continuity failed for district: {district}\n"
                f"Missing dates: {missing_dates.tolist()}\n"
                f"Unexpected dates: {unexpected_dates.tolist()}"
            )

    print("Daily continuity validation: PASSED")

    # ========================================================
    # 8. CHECK EXPECTED RECORD COUNTS
    # ========================================================

    expected_records_per_district = len(expected_dates)

    district_counts = (
        combined_df.groupby("district")
        .size()
    )

    if not (
        district_counts == expected_records_per_district
    ).all():

        raise ValueError(
            "Unexpected number of records per district:\n"
            f"{district_counts}"
        )

    expected_total = (
        EXPECTED_DISTRICTS
        * expected_records_per_district
    )

    if len(combined_df) != expected_total:

        raise ValueError(
            f"Expected {expected_total} records, "
            f"found {len(combined_df)}."
        )

    print("Record count validation: PASSED")

    print(
        "Expected records per district:",
        expected_records_per_district
    )

    # ========================================================
    # 9. CHECK REQUIRED ML FEATURES
    # ========================================================

    for col in REQUIRED_FEATURES:

        if col not in combined_df.columns:

            raise ValueError(
                f"Required model feature missing: {col}"
            )

        if not pd.api.types.is_numeric_dtype(
            combined_df[col]
        ):

            raise ValueError(
                f"Feature is not numeric: {col}"
            )

        if combined_df[col].isna().any():

            raise ValueError(
                f"Missing values found in feature: {col}"
            )

    print("Required ML feature validation: PASSED")

    # ========================================================
    # 10. FINAL DATASET SUMMARY
    # ========================================================

    print("\n" + "=" * 65)
    print("OPERATIONAL DATASET SUMMARY")
    print("=" * 65)

    print("Total records:", len(combined_df))

    print(
        "Total districts:",
        combined_df["district"].nunique()
    )

    print(
        "Start date:",
        combined_df["date"].min().date()
    )

    print(
        "End date:",
        combined_df["date"].max().date()
    )

    print("\nData source counts:")

    print(
        combined_df["data_source"]
        .value_counts()
        .to_string()
    )

    # ========================================================
    # 11. SAVE OPERATIONAL DATASET
    # ========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    combined_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n" + "=" * 65)
    print("OPERATIONAL DATASET CREATED SUCCESSFULLY")
    print("=" * 65)

    print("Saved file:")
    print(OUTPUT_FILE)

    print("\nOriginal ERA5 dataset was not modified.")

    return combined_df


# ============================================================
# 12. MAIN EXECUTION
# ============================================================

if __name__ == "__main__":

    create_operational_dataset()
