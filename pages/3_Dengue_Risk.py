
from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "dengue_forecasting"

PREDICTION_FILE = OUTPUT_DIR / "latest_predictions.csv"

FEATURE_FILE = OUTPUT_DIR / "latest_dengue_features.csv"

HISTORY_FILE = OUTPUT_DIR / "forecast_history.csv"

MAP_FILE = OUTPUT_DIR / "next_week_dengue_map.html"

DENGUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dengue_weekly_25_areas_2025_2026.csv"
)

MODEL_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "forecasting"
    / "riskweave_daily_weather_experiment_model.joblib"
)


# ============================================================
# 2. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Dengue Risk | RiskWeave",
    page_icon="🦟",
    layout="wide"
)


# ============================================================
# 3. CUSTOM STYLING
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #163A5F;
    }

    .sub-title {
        color: #64748b;
        font-size: 1rem;
    }

    .warning-box {
        background-color: #fff7ed;
        border-left: 5px solid #f59e0b;
        padding: 15px;
        border-radius: 5px;
        color: #7c2d12;
    }

    .success-box {
        background-color: #f0fdf4;
        border-left: 5px solid #16a34a;
        padding: 15px;
        border-radius: 5px;
        color: #166534;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 4. DATA LOADING FUNCTIONS
# ============================================================

@st.cache_data
def load_predictions(file_path, modified_time):

    path = Path(file_path)

    if not path.exists():
        return None

    data = pd.read_csv(path)

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

    missing = required_columns - set(data.columns)

    if missing:
        raise ValueError(
            f"Prediction file missing columns: {sorted(missing)}"
        )

    data["predicted_dengue_cases"] = pd.to_numeric(
        data["predicted_dengue_cases"],
        errors="coerce"
    )

    return data


@st.cache_data
def load_forecast_history(file_path, modified_time):

    path = Path(file_path)

    if not path.exists():
        return None

    return pd.read_csv(path)


@st.cache_data
def load_dengue_data(file_path, modified_time):

    path = Path(file_path)

    if not path.exists():
        return None

    return pd.read_csv(path)


# ============================================================
# 5. HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🦟 Dengue Risk Forecasting</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'Climate-informed district-level dengue forecasting '
    'for Sri Lanka'
    '</div>',
    unsafe_allow_html=True
)

st.divider()


# ============================================================
# 6. WEEKLY FORECASTING CONTROL
# ============================================================

st.subheader("Weekly Forecasting Control")

st.write(
    "Run the RiskWeave forecasting pipeline using the latest "
    "available dengue and completed weather data."
)

col1, col2 = st.columns([3, 1])

with col1:

    run_forecast = st.button(
        "🔄 Update Data & Forecast Next Week",
        type="primary",
        use_container_width=True
    )

with col2:

    if st.button(
        "↻ Refresh Dashboard",
        use_container_width=True
    ):
        st.cache_data.clear()
        st.rerun()


if run_forecast:

    required_files = [
        DENGUE_FILE,
        MODEL_FILE,
        PROJECT_ROOT / "data" / "processed"
        / "weather_operational_combined_2006_2026.csv",
    ]

    missing_files = [
        str(path) for path in required_files
        if not path.exists()
    ]

    if missing_files:

        st.error("Some required project files are missing.")

        for file in missing_files:
            st.write(file)

    else:

        with st.spinner(
            "Running RiskWeave weekly forecasting pipeline..."
        ):

            try:

                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "src.dengue_forecasting.weekly_pipeline"
                    ],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    check=True
                )

                st.success(
                    "Forecast pipeline completed successfully."
                )

                with st.expander("Pipeline execution details"):

                    st.code(
                        result.stdout or "No output returned."
                    )

                st.cache_data.clear()

                st.rerun()

            except subprocess.CalledProcessError as error:

                st.error(
                    "The forecasting pipeline failed."
                )

                with st.expander("Error details", expanded=True):

                    st.code(error.stdout or "")
                    st.code(error.stderr or "")

            except Exception as error:

                st.error(
                    f"Unable to execute forecasting pipeline: {error}"
                )


st.divider()


# ============================================================
# 7. LOAD CURRENT OUTPUTS
# ============================================================

try:

    prediction_mtime = (
        PREDICTION_FILE.stat().st_mtime
        if PREDICTION_FILE.exists()
        else 0
    )

    history_mtime = (
        HISTORY_FILE.stat().st_mtime
        if HISTORY_FILE.exists()
        else 0
    )

    dengue_mtime = (
        DENGUE_FILE.stat().st_mtime
        if DENGUE_FILE.exists()
        else 0
    )

    predictions = load_predictions(
        str(PREDICTION_FILE),
        prediction_mtime
    )

    forecast_history = load_forecast_history(
        str(HISTORY_FILE),
        history_mtime
    )

    dengue_data = load_dengue_data(
        str(DENGUE_FILE),
        dengue_mtime
    )

except Exception as error:

    st.error(f"Unable to load RiskWeave data: {error}")
    st.stop()


# ============================================================
# 8. CHECK PREDICTION AVAILABILITY
# ============================================================

if predictions is None:

    st.warning(
        "No dengue predictions are available yet."
    )

    st.info(
        "Use the Update Data & Forecast Next Week button "
        "to run the forecasting pipeline."
    )

    st.stop()


if len(predictions) != 25:

    st.error(
        f"Expected 25 district predictions, "
        f"but found {len(predictions)}."
    )

    st.stop()


if predictions["district_key"].nunique() != 25:

    st.error(
        "Prediction file does not contain 25 unique "
        "RiskWeave reporting areas."
    )

    st.stop()


if predictions["predicted_dengue_cases"].isna().any():

    st.error(
        "Prediction data contains missing or invalid values."
    )

    st.stop()


# ============================================================
# 9. FORECAST INFORMATION
# ============================================================

st.subheader("Forecast Data Status")

first_prediction = predictions.iloc[0]

origin_year = int(
    first_prediction["forecast_origin_year"]
)

origin_week = int(
    first_prediction["forecast_origin_week"]
)

target_year = int(
    first_prediction["target_year"]
)

target_week = int(
    first_prediction["target_week"]
)

target_start = pd.to_datetime(
    first_prediction["target_week_start"]
)

target_end = pd.to_datetime(
    first_prediction["target_week_end"]
)

st.info(
    f"Forecast origin: {origin_year} Week {origin_week} | "
    f"Target: {target_year} Week {target_week} | "
    f"Target dates: {target_start:%d %b %Y} "
    f"to {target_end:%d %b %Y}"
)

# Check that every row belongs to the same forecast
if (
    predictions["target_year"].nunique() != 1
    or predictions["target_week"].nunique() != 1
):
    st.error("Prediction file contains multiple target periods.")
    st.stop()


# Check whether target period has already ended
today = pd.Timestamp.now().normalize()

if target_end < today:

    st.warning(
        "This forecast target period has already ended. "
        "The results are retained for historical analysis. "
        "Upload the latest official dengue report before "
        "generating a new operational forecast."
    )

else:

    st.success(
        "The forecast target period has not yet ended."
    )


# Display latest dengue data coverage
if dengue_data is not None:

    st.write(
        f"Historical dengue records: {len(dengue_data):,}"
    )

    if {"year", "week"}.issubset(dengue_data.columns):

        latest_year = int(dengue_data["year"].max())

        latest_week = int(
            dengue_data.loc[
                dengue_data["year"] == latest_year,
                "week"
            ].max()
        )

        st.caption(
            f"Latest dengue data: {latest_year} "
            f"Week {latest_week}"
        )


st.divider()


# ============================================================
# 10. SUMMARY METRICS
# ============================================================

st.subheader("Dengue Prediction Overview")

total_predicted = predictions[
    "predicted_dengue_cases"
].sum()

average_predicted = predictions[
    "predicted_dengue_cases"
].mean()

highest_row = predictions.loc[
    predictions["predicted_dengue_cases"].idxmax()
]

lowest_row = predictions.loc[
    predictions["predicted_dengue_cases"].idxmin()
]

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Total Predicted Cases",
        f"{total_predicted:,.0f}"
    )

with col2:

    st.metric(
        "Average per District",
        f"{average_predicted:.1f}"
    )

with col3:

    st.metric(
        "Highest Prediction",
        f"{highest_row['predicted_dengue_cases']:.0f}",
        help=str(highest_row["district_key"]).title()
    )

with col4:

    st.metric(
        "Districts Covered",
        predictions["district_key"].nunique()
    )


st.divider()


# ============================================================
# 11. INTERACTIVE SRI LANKA MAP
# ============================================================

st.subheader("Sri Lanka Dengue Prediction Map")

st.write(
    "Explore predicted dengue cases across the 25 "
    "RiskWeave reporting areas."
)

# Only display a map if it was generated after the latest
# prediction file. This prevents displaying an outdated map.

map_is_current = (
    MAP_FILE.exists()
    and PREDICTION_FILE.exists()
    and MAP_FILE.stat().st_mtime >= PREDICTION_FILE.stat().st_mtime
)

if map_is_current:

    try:

        with open(
            MAP_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            map_html = file.read()

        components.html(
            map_html,
            height=650,
            scrolling=True
        )

    except Exception as error:

        st.error(
            f"Unable to display dengue map: {error}"
        )

else:

    st.info(
        "The map has not yet been regenerated for the latest "
        "prediction file. The prediction table below is current."
    )

    st.caption(
        "The map will appear after the map-generation module "
        "is connected to latest_predictions.csv."
    )


st.divider()


# ============================================================
# 12. DISTRICT PREDICTION TABLE
# ============================================================

st.subheader("District-level Dengue Predictions")

display_data = predictions.copy()

display_data["district_key"] = (
    display_data["district_key"]
    .astype(str)
    .str.replace("_", " ")
    .str.title()
)

display_data = display_data.rename(
    columns={
        "district_key": "District",
        "predicted_dengue_cases": "Predicted Cases",
    }
)

display_data = display_data.sort_values(
    "Predicted Cases",
    ascending=False
).reset_index(drop=True)

display_data.index = display_data.index + 1

st.dataframe(
    display_data,
    use_container_width=True,
    height=500
)


# ============================================================
# 13. TOP 10 DISTRICTS
# ============================================================

st.subheader("Top 10 Districts by Predicted Cases")

top_10 = display_data.head(10).sort_values(
    "Predicted Cases",
    ascending=True
)

st.bar_chart(
    top_10.set_index("District")["Predicted Cases"],
    horizontal=True
)


st.divider()


# ============================================================
# 14. FORECAST HISTORY
# ============================================================

st.subheader("Historical Forecast Records")

if forecast_history is not None and not forecast_history.empty:

    st.write(
        "Previously generated forecasts are retained "
        "for future evaluation."
    )

    history_display = forecast_history.copy()

    if {
        "target_year",
        "target_week"
    }.issubset(history_display.columns):

        history_display = history_display.sort_values(
            ["target_year", "target_week"],
            ascending=False
        )

    st.dataframe(
        history_display,
        use_container_width=True,
        height=350
    )

    history_csv = forecast_history.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Download Forecast History",
        data=history_csv,
        file_name="riskweave_forecast_history.csv",
        mime="text/csv"
    )

else:

    st.info(
        "No previous forecast history is available yet."
    )


st.divider()


# ============================================================
# 15. DOWNLOAD LATEST PREDICTIONS
# ============================================================

st.subheader("Download Latest Prediction Results")

csv_data = predictions.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    label="Download District Predictions (CSV)",
    data=csv_data,
    file_name="riskweave_latest_dengue_predictions.csv",
    mime="text/csv"
)


# ============================================================
# 16. MODEL INFORMATION
# ============================================================

with st.expander("Model Information"):

    st.write(
        "**Model:** Histogram Gradient Boosting Regressor"
    )

    st.write(
        "**Model artifact:** "
        "riskweave_daily_weather_experiment_model.joblib"
    )

    st.write(
        "**Input features:** 15"
    )

    st.write(
        "**Prediction coverage:** 25 RiskWeave reporting areas"
    )

    st.write(
        "**Historical test MAE:** Approximately 12.86 cases"
    )

    st.write(
        "**Historical test RMSE:** Approximately 30.69 cases"
    )

    st.caption(
        "These are historical experimental evaluation metrics. "
        "They are not guaranteed current forecasting accuracy."
    )


# ============================================================
# 17. FOOTER
# ============================================================

st.divider()

st.caption(
    "RiskWeave | Climate-informed Dengue Risk Forecasting "
    "and Inspection Planning System | Sri Lanka"
)
