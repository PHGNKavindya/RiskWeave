
import requests
import pandas as pd

API_URL = "https://archive-api.open-meteo.com/v1/archive"

LATITUDE = 7.12490520709576
LONGITUDE = 81.68547230660559

VARIABLES = [
    "precipitation_sum",
    "temperature_2m_mean",
    "relative_humidity_2m_mean"
]

TEST_DATES = [
    ("2016-12-31", "2017-01-02"),
    ("2017-01-01", "2017-01-01"),
    ("2017-01-01", "2017-01-03")
]

for start_date, end_date in TEST_DATES:

    print("\n" + "=" * 60)
    print(f"Testing: {start_date} to {end_date}")
    print("=" * 60)

    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join(VARIABLES),
        "timezone": "Asia/Colombo",
        "models": "ecmwf_ifs",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius"
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=(15, 180)
        )

        response.raise_for_status()

        result = response.json()

        if "daily" not in result:
            print("Daily data missing:", result)
            continue

        df = pd.DataFrame(result["daily"])

        print(df.to_string(index=False))

        print("\nMissing values:")
        print(df[VARIABLES].isna().sum())

        print("\nGrid coordinates:")
        print("Latitude:", result.get("latitude"))
        print("Longitude:", result.get("longitude"))

    except requests.RequestException as error:

        print("API request failed:", error)

print("\nInvestigation completed.")
