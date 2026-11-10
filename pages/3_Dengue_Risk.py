
from pathlib import Path
import json

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Dengue Risk | RiskWeave",
    page_icon="🦟",
    layout="wide"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "dengue_weekly_25_districts.csv"
)

FORECAST_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "forecasting"
    / "next_period_dengue_forecast.csv"
)

MANIFEST_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "forecasting"
    / "riskweave_final_model_manifest.json"
)


# ============================================================
# 2. PAGE HEADER
# ============================================================

st.title("Dengue Risk Prediction")
st.caption(
    "Historical dengue surveillance, district comparisons "
    "and model-generated forecasting results."
)


# ============================================================
# 3. DATA LOADING
# ============================================================

@st.cache_data
def load_dengue_data():
    df = pd.read_csv(DATA_PATH)

    df["week_start"] = pd.to_datetime(df["week_start"])
    df["week_end"] = pd.to_datetime(df["week_end"])

    df["dengue_cases"] = pd.to_numeric(
        df["dengue_cases"],
        errors="coerce"
    )

    return df


@st.cache_data
def load_forecast_data():
    df = pd.read_csv(FORECAST_PATH)

    for col in [
        "forecast_origin_start",
        "forecast_origin_end",
        "forecast_target_start",
        "forecast_target_end"
    ]:
        df[col] = pd.to_datetime(df[col])

    df["predicted_dengue_cases"] = pd.to_numeric(
        df["predicted_dengue_cases"],
        errors="coerce"
    )

    return df


@st.cache_data
def load_model_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


try:
    dengue_df = load_dengue_data()
    forecast_df = load_forecast_data()
    manifest = load_model_manifest()

except FileNotFoundError as error:
    st.error(f"Required RiskWeave file not found: {error}")
    st.stop()

except Exception as error:
    st.error(f"Unable to load dengue data: {error}")
    st.stop()


# ============================================================
# 4. DATA VALIDATION
# ============================================================

required_columns = {
    "district_key",
    "week_start",
    "week_end",
    "dengue_cases"
}

if not required_columns.issubset(dengue_df.columns):
    st.error("The dengue dataset does not contain all required columns.")
    st.stop()

if dengue_df.empty:
    st.warning("The dengue dataset is empty.")
    st.stop()

latest_date = dengue_df["week_end"].max()

latest_period = dengue_df[
    dengue_df["week_end"] == latest_date
].copy()

number_of_districts = dengue_df["district_key"].nunique()

total_latest_cases = latest_period["dengue_cases"].sum()

latest_forecast_date = forecast_df["forecast_target_end"].max()


# ============================================================
# 5. HISTORICAL DATA OVERVIEW
# ============================================================

st.subheader("Historical Dengue Surveillance")

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Reporting Districts",
    f"{number_of_districts}"
)

col2.metric(
    "Historical Records",
    f"{len(dengue_df):,}"
)

col3.metric(
    "Latest Reporting Period",
    latest_date.strftime("%d %b %Y")
)

col4.metric(
    "Latest Period Cases",
    f"{total_latest_cases:,.0f}"
)

st.caption(
    f"Historical dataset coverage: "
    f"{dengue_df['week_start'].min():%d %b %Y} "
    f"to {latest_date:%d %b %Y}"
)


# ============================================================
# 6. DISTRICT FILTER
# ============================================================

st.divider()
st.subheader("District-level Analysis")

districts = sorted(dengue_df["district_key"].dropna().unique())

selected_district = st.selectbox(
    "Select a district",
    ["All Districts"] + districts
)

if selected_district == "All Districts":
    filtered_df = dengue_df.copy()
else:
    filtered_df = dengue_df[
        dengue_df["district_key"] == selected_district
    ].copy()


# ============================================================
# 7. HISTORICAL DENGUE TREND
# ============================================================

st.markdown("#### Weekly Dengue Case Trend")

if selected_district == "All Districts":

    trend_df = (
        filtered_df.groupby("week_start", as_index=False)
        ["dengue_cases"].sum()
    )

    fig = px.line(
        trend_df,
        x="week_start",
        y="dengue_cases",
        title="Weekly Dengue Cases Across Reporting Districts",
        labels={
            "week_start": "Reporting Week",
            "dengue_cases": "Dengue Cases"
        }
    )

else:

    fig = px.line(
        filtered_df.sort_values("week_start"),
        x="week_start",
        y="dengue_cases",
        title=f"Weekly Dengue Cases - {selected_district.title()}",
        labels={
            "week_start": "Reporting Week",
            "dengue_cases": "Dengue Cases"
        }
    )

fig.update_layout(
    hovermode="x unified",
    height=420
)

st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 8. LATEST DISTRICT COMPARISON
# ============================================================

st.markdown("#### Latest Reported Dengue Cases by District")

district_latest = (
    latest_period.groupby("district_key", as_index=False)
    ["dengue_cases"].sum()
    .sort_values("dengue_cases", ascending=False)
)

bar_fig = px.bar(
    district_latest,
    x="district_key",
    y="dengue_cases",
    labels={
        "district_key": "District",
        "dengue_cases": "Reported Dengue Cases"
    },
    title=f"Latest Reporting Period Ending {latest_date:%d %b %Y}"
)

bar_fig.update_layout(
    xaxis_tickangle=-45,
    height=450
)

st.plotly_chart(bar_fig, use_container_width=True)


with st.expander("View latest district-level observations"):
    st.dataframe(
        district_latest,
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# 9. HISTORICAL MODEL FORECAST
# ============================================================

st.divider()
st.subheader("Dengue Forecasting Results")

st.warning(
    "Historical forecast only: the available dengue forecast "
    "was generated using December 2025 observations. It is not "
    "a current November 2026 prediction."
)

st.write(
    f"Forecast origin: "
    f"{forecast_df['forecast_origin_start'].min():%d %b %Y} "
    f"to {forecast_df['forecast_origin_end'].max():%d %b %Y}"
)

st.write(
    f"Forecast target: "
    f"{forecast_df['forecast_target_start'].min():%d %b %Y} "
    f"to {forecast_df['forecast_target_end'].max():%d %b %Y}"
)

forecast_display = forecast_df[
    [
        "district_key",
        "latest_observed_dengue_cases",
        "predicted_dengue_cases"
    ]
].copy()

forecast_display = forecast_display.sort_values(
    "predicted_dengue_cases",
    ascending=False
)

forecast_display.columns = [
    "District",
    "Latest Observed Cases",
    "Predicted Cases"
]

st.dataframe(
    forecast_display,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# 10. MODEL PERFORMANCE
# ============================================================

st.divider()
st.subheader("Dengue Forecasting Model Information")

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "Selected Model",
    manifest["selected_model"]
)

metric2.metric(
    "Test MAE",
    f"{manifest['test_MAE']:.2f}"
)

metric3.metric(
    "Test RMSE",
    f"{manifest['test_RMSE']:.2f}"
)

st.write(
    f"**Selected feature set:** "
    f"{manifest['selected_feature_set']}"
)

st.write(
    f"**Number of predictors:** "
    f"{manifest['number_of_predictors']}"
)

st.write(
    f"**Training observations:** "
    f"{manifest['training_rows']:,}"
)

st.write(
    f"**Validation observations:** "
    f"{manifest['validation_rows']:,}"
)

st.write(
    f"**Test observations:** "
    f"{manifest['test_rows']:,}"
)

st.info(
    "Weather variables were evaluated through an ablation experiment. "
    "The final selected dengue forecasting model uses historical "
    "dengue and seasonal predictors without weather variables."
)

st.caption(
    "MAE and RMSE are historical chronological test-set metrics. "
    "They do not represent current operational forecasting accuracy."
)
