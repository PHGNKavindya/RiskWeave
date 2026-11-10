
from pathlib import Path

import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PREDICTION_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "dengue_forecasting"
    / "next_week_dengue_predictions.csv"
)

GEOJSON_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "geographical_inspection"
    / "district_dengue_forecast.geojson"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "outputs"
    / "dengue_forecasting"
)

MAP_FILE = OUTPUT_DIR / "next_week_dengue_map.html"


# ============================================================
# 2. LOAD DATA
# ============================================================

def load_data():

    print("\nLoading prediction and geographical data...")

    if not PREDICTION_FILE.exists():
        raise FileNotFoundError(
            f"Prediction file not found:\n{PREDICTION_FILE}"
        )

    if not GEOJSON_FILE.exists():
        raise FileNotFoundError(
            f"Geographical file not found:\n{GEOJSON_FILE}"
        )

    predictions = pd.read_csv(PREDICTION_FILE)

    districts = gpd.read_file(GEOJSON_FILE)

    required_prediction_columns = {
        "district_key",
        "predicted_dengue_cases"
    }

    missing = (
        required_prediction_columns
        - set(predictions.columns)
    )

    if missing:
        raise ValueError(
            f"Missing prediction columns: {sorted(missing)}"
        )

    if "district_key" not in districts.columns:
        raise ValueError(
            "The geographical dataset must contain district_key."
        )

    predictions["district_key"] = (
        predictions["district_key"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    districts["district_key"] = (
        districts["district_key"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    predictions["predicted_dengue_cases"] = pd.to_numeric(
        predictions["predicted_dengue_cases"],
        errors="coerce"
    )

    if predictions["predicted_dengue_cases"].isna().any():
        raise ValueError(
            "Prediction dataset contains invalid case counts."
        )

    if predictions["district_key"].duplicated().any():
        raise ValueError(
            "Duplicate district keys found in predictions."
        )

    if districts["district_key"].duplicated().any():
        raise ValueError(
            "Duplicate district keys found in geographical data."
        )

    print("Prediction records:", len(predictions))
    print("Geographical records:", len(districts))

    return predictions, districts


# ============================================================
# 3. MERGE PREDICTIONS WITH DISTRICT GEOGRAPHY
# ============================================================

def prepare_map_data(predictions, districts):

    print("\nMatching district predictions...")

    # Remove old prediction column if present.
    districts = districts.drop(
        columns=["predicted_dengue_cases"],
        errors="ignore"
    )

    map_data = districts.merge(
        predictions,
        on="district_key",
        how="left",
        validate="one_to_one"
    )

    missing_predictions = map_data[
        map_data["predicted_dengue_cases"].isna()
    ]

    if not missing_predictions.empty:

        missing = missing_predictions[
            "district_key"
        ].tolist()

        raise ValueError(
            f"Predictions missing for districts: {missing}"
        )

    prediction_districts = set(predictions["district_key"])
    map_districts = set(map_data["district_key"])

    if prediction_districts != map_districts:

        raise ValueError(
            "District mismatch between prediction and map datasets."
        )

    if len(map_data) != 25:

        raise ValueError(
            f"Expected 25 districts, found {len(map_data)}"
        )

    # Folium requires a geographic coordinate system.
    if map_data.crs is None:
        raise ValueError(
            "Geographical dataset has no CRS defined."
        )

    if map_data.crs.to_epsg() != 4326:
        map_data = map_data.to_crs(epsg=4326)

    print("Successfully matched all 25 districts.")

    return map_data


# ============================================================
# 4. CREATE DENGUE MAP
# ============================================================

def create_map(map_data):

    print("\nCreating interactive dengue map...")

    minimum = float(
        map_data["predicted_dengue_cases"].min()
    )

    maximum = float(
        map_data["predicted_dengue_cases"].max()
    )

    if minimum == maximum:
        maximum = minimum + 1

    # Colour scale.
    colour_scale = cm.LinearColormap(
        colors=[
            "#ffffcc",
            "#ffeda0",
            "#feb24c",
            "#fd8d3c",
            "#f03b20",
            "#bd0026"
        ],
        vmin=minimum,
        vmax=maximum,
        caption="Predicted dengue cases"
    )

    # Base map.
    dengue_map = folium.Map(
        location=[7.8, 80.7],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True
    )

    # District styling.
    def district_style(feature):

        cases = feature["properties"][
            "predicted_dengue_cases"
        ]

        return {
            "fillColor": colour_scale(cases),
            "color": "#333333",
            "weight": 1,
            "fillOpacity": 0.75
        }

    # Tooltip.
    tooltip = folium.GeoJsonTooltip(
        fields=[
            "district_key",
            "predicted_dengue_cases"
        ],
        aliases=[
            "District:",
            "Predicted dengue cases:"
        ],
        localize=True,
        sticky=True
    )

    # Popup.
    popup = folium.GeoJsonPopup(
        fields=[
            "district_key",
            "predicted_dengue_cases"
        ],
        aliases=[
            "District:",
            "Predicted dengue cases:"
        ],
        localize=True
    )

    # Convert GeoDataFrame to GeoJSON.
    # Convert timestamps and other non-JSON values safely.
    geojson_data = map_data.copy()

    for column in geojson_data.columns:

        if column == "geometry":
            continue

        if pd.api.types.is_datetime64_any_dtype(
            geojson_data[column]
        ):
            geojson_data[column] = (
                geojson_data[column].astype(str)
            )

        elif geojson_data[column].dtype == "object":

            geojson_data[column] = geojson_data[column].apply(
                lambda value: (
                    value.isoformat()
                    if isinstance(value, pd.Timestamp)
                    else value
                )
            )

    geojson_string = geojson_data.to_json(
        na="drop",
        drop_id=True
    )

    # Add district polygons.
    folium.GeoJson(
        geojson_string,
        name="Dengue predictions",
        style_function=district_style,
        tooltip=tooltip,
        popup=popup,
        highlight_function=lambda feature: {
            "weight": 3,
            "color": "#000000",
            "fillOpacity": 0.9
        }
    ).add_to(dengue_map)

    # Add legend.
    colour_scale.add_to(dengue_map)

    # Layer control.
    folium.LayerControl().add_to(dengue_map)

    # Map title.
    title_html = """
    <div style="
        position: fixed;
        top: 10px;
        left: 50px;
        z-index: 9999;
        background-color: white;
        padding: 12px 18px;
        border-radius: 6px;
        border: 1px solid #cccccc;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    ">
        <h4 style="margin: 0; color: #263238;">
            RiskWeave - Dengue Case Predictions
        </h4>
        <p style="margin: 4px 0 0 0; font-size: 11px;">
            Historical-input model output; not a live 2026 forecast
        </p>
    </div>
    """

    dengue_map.get_root().html.add_child(
        folium.Element(title_html)
    )

    # Fit map to Sri Lankan district boundaries.
    minx, miny, maxx, maxy = map_data.total_bounds

    dengue_map.fit_bounds([
        [miny, minx],
        [maxy, maxx]
    ])

    return dengue_map


# ============================================================
# 5. SAVE MAP
# ============================================================

def save_map(dengue_map):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    dengue_map.save(str(MAP_FILE))

    print("\nMAP SAVED SUCCESSFULLY")
    print("----------------------")
    print("Location:", MAP_FILE)


# ============================================================
# 6. MAIN
# ============================================================

def main():

    print("\n" + "=" * 55)
    print("RISKWEAVE DENGUE PREDICTION MAP")
    print("=" * 55)

    predictions, districts = load_data()

    map_data = prepare_map_data(
        predictions,
        districts
    )

    dengue_map = create_map(map_data)

    save_map(dengue_map)

    print("\nMAP GENERATION COMPLETED.")
    print("Districts displayed:", len(map_data))


if __name__ == "__main__":
    main()
