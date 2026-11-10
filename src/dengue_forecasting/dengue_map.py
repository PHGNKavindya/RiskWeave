
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
    / "latest_predictions.csv"
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

EXPECTED_DISTRICTS = 25


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

    required_columns = {
        "district_key",
        "predicted_dengue_cases",
        "forecast_origin_year",
        "forecast_origin_week",
        "target_year",
        "target_week",
        "target_week_start",
        "target_week_end",
    }

    missing = required_columns - set(predictions.columns)

    if missing:
        raise ValueError(
            f"Missing prediction columns: {sorted(missing)}"
        )

    if "district_key" not in districts.columns:
        raise ValueError(
            "Geographical dataset must contain district_key."
        )

    # Standardize district keys
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

    # Convert predictions to numeric values
    predictions["predicted_dengue_cases"] = pd.to_numeric(
        predictions["predicted_dengue_cases"],
        errors="coerce"
    )

    if predictions["predicted_dengue_cases"].isna().any():
        raise ValueError(
            "Invalid predicted dengue case values found."
        )

    if predictions["district_key"].duplicated().any():
        raise ValueError(
            "Duplicate district keys in prediction data."
        )

    if districts["district_key"].duplicated().any():
        raise ValueError(
            "Duplicate district keys in geographical data."
        )

    if len(predictions) != EXPECTED_DISTRICTS:
        raise ValueError(
            f"Expected 25 predictions, found {len(predictions)}."
        )

    if predictions["district_key"].nunique() != EXPECTED_DISTRICTS:
        raise ValueError(
            "Expected 25 unique RiskWeave reporting areas."
        )

    # Display cases as whole numbers.
    predictions["predicted_dengue_cases"] = (
        predictions["predicted_dengue_cases"]
        .clip(lower=0)
        .round()
        .astype(int)
    )

    print("Prediction records:", len(predictions))
    print("Geographical records:", len(districts))

    return predictions, districts


# ============================================================
# 3. MERGE PREDICTIONS WITH DISTRICT GEOGRAPHY
# ============================================================

def prepare_map_data(predictions, districts):

    print("\nMatching district predictions...")

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

    if map_data["predicted_dengue_cases"].isna().any():

        missing = map_data.loc[
            map_data["predicted_dengue_cases"].isna(),
            "district_key"
        ].tolist()

        raise ValueError(
            f"Missing predictions for districts: {missing}"
        )

    prediction_districts = set(predictions["district_key"])
    map_districts = set(map_data["district_key"])

    if prediction_districts != map_districts:
        raise ValueError(
            "District mismatch between predictions and geography."
        )

    if len(map_data) != EXPECTED_DISTRICTS:
        raise ValueError(
            f"Expected 25 mapped districts, found {len(map_data)}."
        )

    if map_data.crs is None:
        raise ValueError(
            "Geographical dataset has no CRS defined."
        )

    if map_data.crs.to_epsg() != 4326:
        map_data = map_data.to_crs(epsg=4326)

    # Ensure integer values after merging
    map_data["predicted_dengue_cases"] = (
        map_data["predicted_dengue_cases"]
        .round()
        .astype(int)
    )

    print("Successfully matched all 25 districts.")

    return map_data


# ============================================================
# 4. GET FORECAST INFORMATION
# ============================================================

def get_forecast_information(predictions):

    row = predictions.iloc[0]

    origin_year = int(row["forecast_origin_year"])
    origin_week = int(row["forecast_origin_week"])

    target_year = int(row["target_year"])
    target_week = int(row["target_week"])

    target_start = pd.to_datetime(
        row["target_week_start"]
    )

    target_end = pd.to_datetime(
        row["target_week_end"]
    )

    today = pd.Timestamp.now().normalize()

    if target_end < today:
        status = "Historical forecast test"
    else:
        status = "Model prediction"

    return {
        "origin_year": origin_year,
        "origin_week": origin_week,
        "target_year": target_year,
        "target_week": target_week,
        "target_start": target_start,
        "target_end": target_end,
        "status": status,
    }


# ============================================================
# 5. CREATE INTERACTIVE DENGUE MAP
# ============================================================

def create_map(map_data, forecast_info):

    print("\nCreating interactive dengue map...")

    minimum = int(
        map_data["predicted_dengue_cases"].min()
    )

    maximum = int(
        map_data["predicted_dengue_cases"].max()
    )

    if minimum == maximum:
        maximum = minimum + 1

    # --------------------------------------------------------
    # COLOUR SCALE
    # --------------------------------------------------------

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
        caption="Predicted dengue cases (whole cases)"
    )

    # --------------------------------------------------------
    # BASE MAP
    # --------------------------------------------------------

    dengue_map = folium.Map(
        location=[7.8, 80.7],
        zoom_start=7,
        tiles="OpenStreetMap",
        control_scale=True
    )

    # --------------------------------------------------------
    # DISTRICT STYLE
    # --------------------------------------------------------

    def district_style(feature):

        cases = int(
            feature["properties"]["predicted_dengue_cases"]
        )

        return {
            "fillColor": colour_scale(cases),
            "color": "#333333",
            "weight": 1,
            "fillOpacity": 0.75
        }

    # --------------------------------------------------------
    # TOOLTIP
    # --------------------------------------------------------

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
        sticky=True,
        labels=True
    )

    # --------------------------------------------------------
    # POPUP
    # --------------------------------------------------------

    popup = folium.GeoJsonPopup(
        fields=[
            "district_key",
            "predicted_dengue_cases"
        ],
        aliases=[
            "District:",
            "Predicted dengue cases:"
        ],
        localize=True,
        labels=True
    )

    # --------------------------------------------------------
    # PREPARE GEOJSON
    # --------------------------------------------------------

    geojson_data = map_data.copy()

    # Remove unnecessary geometry-independent data types
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

            geojson_data[column] = (
                geojson_data[column].apply(
                    lambda value: (
                        value.isoformat()
                        if isinstance(value, pd.Timestamp)
                        else value
                    )
                )
            )

    geojson_string = geojson_data.to_json(
        na="drop",
        drop_id=True
    )

    # --------------------------------------------------------
    # ADD DISTRICT POLYGONS
    # --------------------------------------------------------

    folium.GeoJson(
        geojson_string,
        name="Dengue case predictions",
        style_function=district_style,
        tooltip=tooltip,
        popup=popup,
        highlight_function=lambda feature: {
            "weight": 3,
            "color": "#000000",
            "fillOpacity": 0.9
        }
    ).add_to(dengue_map)

    # --------------------------------------------------------
    # ADD LEGEND
    # --------------------------------------------------------

    colour_scale.add_to(dengue_map)

    # --------------------------------------------------------
    # ADD MAP TITLE AND FORECAST PERIOD
    # --------------------------------------------------------

    title_html = f"""
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
        max-width: 380px;
    ">

        <h4 style="
            margin: 0;
            color: #263238;
            font-size: 15px;
        ">
            RiskWeave - Dengue Case Predictions
        </h4>

        <p style="
            margin: 5px 0 0 0;
            font-size: 11px;
            color: #555555;
        ">
            {forecast_info['status']}
        </p>

        <p style="
            margin: 4px 0 0 0;
            font-size: 11px;
            color: #555555;
        ">
            Forecast origin:
            {forecast_info['origin_year']}
            Week {forecast_info['origin_week']}
        </p>

        <p style="
            margin: 4px 0 0 0;
            font-size: 11px;
            color: #555555;
        ">
            Target:
            {forecast_info['target_year']}
            Week {forecast_info['target_week']}
        </p>

        <p style="
            margin: 4px 0 0 0;
            font-size: 11px;
            color: #555555;
        ">
            {forecast_info['target_start']:%d %b %Y}
            to
            {forecast_info['target_end']:%d %b %Y}
        </p>

    </div>
    """

    dengue_map.get_root().html.add_child(
        folium.Element(title_html)
    )

    # --------------------------------------------------------
    # FIT MAP TO SRI LANKA
    # --------------------------------------------------------

    minx, miny, maxx, maxy = map_data.total_bounds

    dengue_map.fit_bounds([
        [miny, minx],
        [maxy, maxx]
    ])

    # --------------------------------------------------------
    # LAYER CONTROL
    # --------------------------------------------------------

    folium.LayerControl().add_to(dengue_map)

    return dengue_map


# ============================================================
# 6. SAVE MAP
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
# 7. MAIN
# ============================================================

def main():

    print("\n" + "=" * 55)
    print("RISKWEAVE DENGUE PREDICTION MAP")
    print("=" * 55)

    predictions, districts = load_data()

    forecast_info = get_forecast_information(
        predictions
    )

    map_data = prepare_map_data(
        predictions,
        districts
    )

    dengue_map = create_map(
        map_data,
        forecast_info
    )

    save_map(dengue_map)

    print("\nMAP GENERATION COMPLETED")
    print("Districts displayed:", len(map_data))

    print(
        "Forecast target:",
        forecast_info["target_year"],
        "Week",
        forecast_info["target_week"]
    )

    print(
        "Predicted cases range:",
        map_data["predicted_dengue_cases"].min(),
        "to",
        map_data["predicted_dengue_cases"].max()
    )


if __name__ == "__main__":
    main()
