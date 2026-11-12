
from pathlib import Path
import time
import requests
import pandas as pd

# ============================================================
# RISKWEAVE - ECMWF IFS COMPARISON DATA COLLECTION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

COORDINATES_FILE = (
    PROJECT_ROOT
    / "data"
    / "reference"
    / "district_coordinates.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "environmental_anomalies"
    / "ifs_district_data"
)

FINAL_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "environmental_anomalies"
    / "ifs_comparison_2024_2025.csv"
)

API_URL = "https://archive-api.open-meteo.com/v1/archive"

START_DATE = "2024-01-01"
END_DATE = "2025-12-31"

EXPECTED_DISTRICTS = 25
EXPECTED_RECORDS = 731

WEATHER_VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 1. LOAD DISTRICT COORDINATES
# ============================================================

coordinates = pd.read_csv(COORDINATES_FILE)

required_coordinate_columns = [
    "district",
    "latitude",
    "longitude"
]

if not set(required_coordinate_columns).issubset(
    coordinates.columns
):
    raise ValueError(
        "District coordinate file is missing required columns."
    )

if len(coordinates) != EXPECTED_DISTRICTS:
    raise ValueError(
        f"Expected {EXPECTED_DISTRICTS} districts, "
        f"found {len(coordinates)}."
    )

if coordinates["district"].duplicated().any():
    raise ValueError("Duplicate district names found.")

if coordinates[
    ["district", "latitude", "longitude"]
].isna().any().any():
    raise ValueError("Missing district coordinate values.")

# ============================================================
# 2. EXPECTED DATE SEQUENCE
# ============================================================

expected_dates = pd.date_range(
    START_DATE,
    END_DATE,
    freq="D"
)

if len(expected_dates) != EXPECTED_RECORDS:
    raise ValueError("Unexpected comparison date count.")

# ============================================================
# 3. COLLECT ONE DISTRICT
# ============================================================

def collect_district(session, district_row):

    district = str(district_row["district"])
    latitude = float(district_row["latitude"])
    longitude = float(district_row["longitude"])

    output_file = OUTPUT_DIR / f"{district.lower().replace(' ', '_')}_ifs.csv"

    # Reuse an existing validated checkpoint.
    if output_file.exists():

        existing = pd.read_csv(output_file)

        existing["date"] = pd.to_datetime(
            existing["date"],
            errors="coerce"
        )

        if (
            len(existing) == EXPECTED_RECORDS
            and existing["date"].equals(
                pd.Series(expected_dates, name="date")
            )
            and existing["district"].eq(district).all()
        ):
            print(f"Using validated checkpoint: {district}")
            return existing

        print(f"Existing checkpoint needs recollection: {district}")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(WEATHER_VARIABLES),
        "timezone": "Asia/Colombo",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "models": "ecmwf_ifs"
    }

    print(f"\nCollecting: {district}")

    response_data = None

    for attempt in range(1, 4):

        try:

            response = session.get(
                API_URL,
                params=params,
                timeout=(15, 180)
            )

            response.raise_for_status()

            response_data = response.json()

            if response_data.get("error"):
                raise RuntimeError(
                    response_data.get("reason", "API error")
                )

            break

        except Exception as error:

            print(
                f"Attempt {attempt}/3 failed for {district}: "
                f"{error}"
            )

            if attempt == 3:
                raise RuntimeError(
                    f"Collection failed for {district}."
                ) from error

            wait_seconds = 10 * attempt

            print(
                f"Waiting {wait_seconds} seconds before retry..."
            )

            time.sleep(wait_seconds)

    daily = response_data.get("daily")

    if not daily:
        raise ValueError(
            f"No daily weather data returned for {district}."
        )

    df = pd.DataFrame(daily)

    df = df.rename(columns={"time": "date"})

    required_columns = [
        "date",
        *WEATHER_VARIABLES
    ]

    if not set(required_columns).issubset(df.columns):
        raise ValueError(
            f"Missing API variables for {district}."
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df["district"] = district

    df["data_source"] = "Open-Meteo ECMWF IFS"

    df["model"] = "ecmwf_ifs"

    df["requested_latitude"] = latitude
    df["requested_longitude"] = longitude

    df["ifs_grid_latitude"] = response_data.get("latitude")
    df["ifs_grid_longitude"] = response_data.get("longitude")
    df["ifs_grid_elevation_m"] = response_data.get("elevation")

    # Convert weather variables to numeric.
    for column in WEATHER_VARIABLES:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # Validate date coverage.
    actual_dates = pd.DatetimeIndex(df["date"])

    if len(df) != EXPECTED_RECORDS:
        raise ValueError(
            f"{district}: expected {EXPECTED_RECORDS} records, "
            f"received {len(df)}."
        )

    if actual_dates.has_duplicates:
        raise ValueError(
            f"{district}: duplicate dates found."
        )

    missing_dates = expected_dates.difference(actual_dates)

    unexpected_dates = actual_dates.difference(expected_dates)

    if len(missing_dates) or len(unexpected_dates):
        raise ValueError(
            f"{district}: incorrect date coverage."
        )

    if df[WEATHER_VARIABLES].isna().any().any():
        raise ValueError(
            f"{district}: missing weather values found."
        )

    # Validate physical ranges.
    if (df["precipitation_sum"] < 0).any():
        raise ValueError(
            f"{district}: negative rainfall found."
        )

    if not df["relative_humidity_2m_mean"].between(
        0, 100
    ).all():
        raise ValueError(
            f"{district}: humidity outside 0-100%."
        )

    df = df.sort_values("date").reset_index(drop=True)

    # Save validated district checkpoint.
    df.to_csv(output_file, index=False)

    print(
        f"Completed {district}: {len(df)} records"
    )

    return df


# ============================================================
# 4. COLLECT ALL 25 DISTRICTS
# ============================================================

def main():

    print("=" * 65)
    print("RISKWEAVE ECMWF IFS DATA COLLECTION")
    print("=" * 65)

    collected_frames = []

    with requests.Session() as session:

        session.headers.update({
            "User-Agent": "RiskWeave-Research-Project/1.0"
        })

        for _, district_row in coordinates.iterrows():

            district_df = collect_district(
                session,
                district_row
            )

            collected_frames.append(district_df)

            # Avoid sending requests too rapidly.
            time.sleep(1)

    # ========================================================
    # 5. COMBINE DATASETS
    # ========================================================

    combined = pd.concat(
        collected_frames,
        ignore_index=True
    )

    combined = combined.sort_values(
        ["district", "date"]
    ).reset_index(drop=True)

    # ========================================================
    # 6. FINAL VALIDATION
    # ========================================================

    print("\n" + "=" * 65)
    print("FINAL COLLECTION VALIDATION")
    print("=" * 65)

    print("Total records:", len(combined))
    print("Total districts:", combined["district"].nunique())

    print(
        "Date range:",
        combined["date"].min(),
        "to",
        combined["date"].max()
    )

    print(
        "Duplicate district-date records:",
        combined.duplicated(
            subset=["district", "date"]
        ).sum()
    )

    print("\nRecords per district:")
    print(combined.groupby("district").size())

    expected_total = (
        EXPECTED_DISTRICTS * EXPECTED_RECORDS
    )

    if len(combined) != expected_total:
        raise ValueError("Incorrect total record count.")

    if combined["district"].nunique() != EXPECTED_DISTRICTS:
        raise ValueError("Incorrect district count.")

    if combined.duplicated(
        subset=["district", "date"]
    ).any():
        raise ValueError("Duplicate district-date records.")

    if combined[WEATHER_VARIABLES].isna().any().any():
        raise ValueError("Missing weather values.")

    # ========================================================
    # 7. SAVE FINAL DATASET
    # ========================================================

    combined.to_csv(
        FINAL_OUTPUT,
        index=False
    )

    print("\n" + "=" * 65)
    print("COLLECTION COMPLETED SUCCESSFULLY")
    print("=" * 65)

    print("Saved dataset:")
    print(FINAL_OUTPUT)


if __name__ == "__main__":
    main()
