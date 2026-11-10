
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PREDICTION_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "dengue_forecasting"
    / "next_week_dengue_predictions.csv"
)

MAP_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "dengue_forecasting"
    / "next_week_dengue_map.html"
)

DENGUE_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dengue_weekly_25_districts.csv"
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

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 4. LOAD DATA
# ============================================================

@st.cache_data
def load_predictions():

    if not PREDICTION_FILE.exists():
        return None

    data = pd.read_csv(PREDICTION_FILE)

    required_columns = {
        "district_key",
        "predicted_dengue_cases"
    }

    if not required_columns.issubset(data.columns):
        raise ValueError(
            "Prediction file has missing columns."
        )

    return data


@st.cache_data
def load_latest_dengue_date():

    if not DENGUE_FILE.exists():
        return None

    dengue = pd.read_csv(DENGUE_FILE)

    dengue["week_start"] = pd.to_datetime(
        dengue["week_start"],
        errors="coerce"
    )

    return dengue["week_start"].max()


# ============================================================
# 5. HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🦟 Dengue Risk Forecasting</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub-title">'
    'District-level dengue case predictions for Sri Lanka'
    '</div>',
    unsafe_allow_html=True
)

st.divider()


# ============================================================
# 6. LOAD CURRENT OUTPUTS
# ============================================================

try:

    predictions = load_predictions()
    latest_dengue_date = load_latest_dengue_date()

except Exception as error:

    st.error(f"Unable to load dengue data: {error}")
    st.stop()


if predictions is None:

    st.warning(
        "Dengue predictions are not available. "
        "Run the dengue prediction module first."
    )

    st.code(
        "python -m src.dengue_forecasting.dengue_predictions"
    )

    st.stop()


if len(predictions) != 25:

    st.error(
        f"Expected 25 district predictions, "
        f"but found {len(predictions)}."
    )

    st.stop()


if predictions["predicted_dengue_cases"].isna().any():

    st.error("Prediction data contains missing values.")
    st.stop()


# ============================================================
# 7. FORECAST DATA STATUS
# ============================================================

st.subheader("Forecast Data Status")

if latest_dengue_date is not None:

    st.info(
        f"Latest dengue reporting period starts: "
        f"{latest_dengue_date.strftime('%d %B %Y')}"
    )

    st.markdown(
        """
        <div class="warning-box">
        <strong>Historical-input forecast</strong><br>
        These predictions use dengue case features from the latest
        available historical reporting period. They are not yet
        validated as current November 2026 forecasts using live
        weather inputs.
        </div>
        """,
        unsafe_allow_html=True
    )

else:

    st.warning(
        "The latest dengue reporting date could not be determined."
    )


# ============================================================
# 8. SUMMARY METRICS
# ============================================================

total_predicted = int(
    predictions["predicted_dengue_cases"].sum()
)

average_predicted = predictions[
    "predicted_dengue_cases"
].mean()

highest_district_row = predictions.loc[
    predictions["predicted_dengue_cases"].idxmax()
]

highest_district = highest_district_row["district_key"]

highest_cases = int(
    highest_district_row["predicted_dengue_cases"]
)

lowest_district_row = predictions.loc[
    predictions["predicted_dengue_cases"].idxmin()
]

lowest_district = lowest_district_row["district_key"]

lowest_cases = int(
    lowest_district_row["predicted_dengue_cases"]
)


st.subheader("Dengue Prediction Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Predicted Cases",
        f"{total_predicted:,}"
    )

with col2:
    st.metric(
        "Average per District",
        f"{average_predicted:.1f}"
    )

with col3:
    st.metric(
        "Highest Prediction",
        f"{highest_cases:,}",
        help=highest_district.title()
    )

with col4:
    st.metric(
        "Districts Covered",
        len(predictions)
    )


st.divider()


# ============================================================
# 9. INTERACTIVE SRI LANKA MAP
# ============================================================

st.subheader("Sri Lanka Dengue Prediction Map")

st.write(
    "Explore predicted dengue case counts across all 25 districts. "
    "Select a district on the map to see its prediction."
)

if MAP_FILE.exists():

    try:

        with open(MAP_FILE, "r", encoding="utf-8") as file:
            map_html = file.read()

        components.html(
            map_html,
            height=650,
            scrolling=False
        )

    except Exception as error:

        st.error(f"Unable to display dengue map: {error}")

else:

    st.warning(
        "Dengue map has not been generated yet."
    )

    st.code(
        "python -m src.dengue_forecasting.dengue_map"
    )


st.divider()


# ============================================================
# 10. DISTRICT PREDICTION TABLE
# ============================================================

st.subheader("District-level Dengue Predictions")

display_data = predictions.copy()

display_data["district_key"] = (
    display_data["district_key"]
    .str.replace("_", " ")
    .str.title()
)

display_data = display_data.rename(
    columns={
        "district_key": "District",
        "predicted_dengue_cases": "Predicted Cases"
    }
)

display_data = display_data.sort_values(
    "Predicted Cases",
    ascending=False
).reset_index(drop=True)

display_data.index = display_data.index + 1

st.dataframe(
    display_data,
    use_container_width=True
)


# ============================================================
# 11. TOP 10 DISTRICTS
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


# ============================================================
# 12. DOWNLOAD PREDICTIONS
# ============================================================

st.divider()

st.subheader("Download Prediction Results")

csv_data = predictions.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download District Predictions (CSV)",
    data=csv_data,
    file_name="riskweave_dengue_predictions.csv",
    mime="text/csv"
)


# ============================================================
# 13. MODEL INFORMATION
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
        "**Prediction coverage:** 25 Sri Lankan districts"
    )

    st.write(
        "**Training data:** Historical dengue and weather data "
        "through December 2025"
    )

    st.write(
        "**Historical test MAE:** Approximately 12.86 cases"
    )

    st.write(
        "**Historical test RMSE:** Approximately 30.69 cases"
    )

    st.caption(
        "These are historical experiment metrics, not guaranteed "
        "current forecasting accuracy."
    )


# ============================================================
# 14. FOOTER
# ============================================================

st.divider()

st.caption(
    "RiskWeave | Climate-informed Dengue Risk Forecasting "
    "and Inspection Planning System | Sri Lanka"
)
