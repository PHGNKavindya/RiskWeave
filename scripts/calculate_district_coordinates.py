
import requests
import geopandas as gpd
import pandas as pd
from pathlib import Path

# --------------------------------------------------
# 1. Define project folders
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parents[1]

RAW_DIR = PROJECT_DIR / "data" / "raw"
REFERENCE_DIR = PROJECT_DIR / "data" / "reference"

RAW_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# 2. Official Sri Lanka NSDI district boundary API
# --------------------------------------------------

API_URL = (
    "https://gisapps.nsdi.gov.lk/server/rest/services/"
    "Srilanka/Boundaries/MapServer/3/query"
)

params = {
    "where": "1=1",
    "outFields": "*",
    "returnGeometry": "true",
    "outSR": "4326",
    "f": "geojson"
}

print("Downloading district boundary polygons...")

response = requests.get(API_URL, params=params, timeout=60)
response.raise_for_status()

geojson_data = response.json()

if "features" not in geojson_data:
    raise ValueError(f"Unexpected API response: {geojson_data}")

if not geojson_data["features"]:
    raise ValueError("No district polygons were returned.")

# Save the original downloaded boundary data
raw_file = RAW_DIR / "district_boundaries.geojson"

with open(raw_file, "w", encoding="utf-8") as file:
    import json
    json.dump(geojson_data, file, ensure_ascii=False)

print("Boundary file saved:", raw_file)

# --------------------------------------------------
# 3. Convert GeoJSON into a GeoDataFrame
# --------------------------------------------------

districts = gpd.GeoDataFrame.from_features(
    geojson_data["features"],
    crs="EPSG:4326"
)

# Check required columns
if "district_name" not in districts.columns:
    raise ValueError(
        "The expected district_name field was not found."
    )

# Remove empty geometries
districts = districts[
    districts.geometry.notna() &
    ~districts.geometry.is_empty
].copy()

# Check and repair invalid geometries if necessary
invalid_count = (~districts.geometry.is_valid).sum()

if invalid_count > 0:
    print(f"Repairing {invalid_count} invalid geometries...")
    districts["geometry"] = districts.geometry.make_valid()

# Keep only polygon geometries
districts = districts[
    districts.geometry.geom_type.isin(
        ["Polygon", "MultiPolygon"]
    )
].copy()

# --------------------------------------------------
# 4. Check district count
# --------------------------------------------------

districts["district_name"] = (
    districts["district_name"].astype(str).str.strip()
)

districts = districts.drop_duplicates(
    subset="district_name"
).copy()

print("Number of unique districts:", len(districts))

if len(districts) != 25:
    raise ValueError(
        f"Expected 25 districts, but found {len(districts)}. "
        "Check the downloaded boundary data before continuing."
    )

# --------------------------------------------------
# 5. Calculate representative points
# --------------------------------------------------

# Sri Lanka lies within UTM Zone 44N for this workflow.
# Project the polygons before calculating the points.
districts_projected = districts.to_crs("EPSG:32644")

districts_projected["representative_geometry"] = (
    districts_projected.geometry.representative_point()
)

# Convert representative points back to latitude/longitude
points = gpd.GeoDataFrame(
    districts_projected.drop(columns="geometry"),
    geometry="representative_geometry",
    crs="EPSG:32644"
).to_crs("EPSG:4326")

# Extract coordinates
points["longitude"] = points.geometry.x
points["latitude"] = points.geometry.y

# --------------------------------------------------
# 6. Create the district reference CSV
# --------------------------------------------------

coordinates = points[
    [
        "district_name",
        "latitude",
        "longitude"
    ]
].copy()

coordinates = coordinates.rename(
    columns={"district_name": "district"}
)

coordinates["coordinate_method"] = "representative_point"
coordinates["coordinate_crs"] = "EPSG:4326"
coordinates["boundary_source"] = "Sri Lanka NSDI"

coordinates = coordinates.sort_values(
    "district"
).reset_index(drop=True)

output_file = (
    REFERENCE_DIR / "district_coordinates.csv"
)

coordinates.to_csv(
    output_file,
    index=False,
    encoding="utf-8-sig"
)

# --------------------------------------------------
# 7. Display and verify results
# --------------------------------------------------

print("\nRepresentative district coordinates:")
print(coordinates.to_string(index=False))

print("\nFinal district count:", len(coordinates))
print("Missing latitude values:", coordinates["latitude"].isna().sum())
print("Missing longitude values:", coordinates["longitude"].isna().sum())

print("\nCSV successfully saved to:")
print(output_file)
