
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

# ==================================================
# 1. PROJECT PATHS
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

LIVE_WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "weather_live"
    / "dashboard_weather_forecasts.csv"
)

HISTORICAL_WEATHER_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "weather_era5_combined_2006_2026.csv"
)

ML_PREDICTIONS_FILE = (
    PROJECT_ROOT
    / "outputs"
    / "weather_forecasting"
    / "operational"
    / "latest_ml_weather_predictions.csv"
)

from weather_forecasting.live_weather import update_live_weather


# ==================================================
# 2. PAGE HEADER
# ==================================================

st.title("🌦️ Weather Forecasting")

st.caption(
    "Today's weather, historical ERA5 patterns, "
    "and RiskWeave machine-learning predictions "
    "across 25 districts of Sri Lanka."
)

st.divider()

today = pd.Timestamp.now(
    tz="Asia/Colombo"
).date()


# ==================================================
# 3. DATA LOADING FUNCTIONS
# ==================================================

@st.cache_data(ttl=1800)
def load_live_weather():

    if not LIVE_WEATHER_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(LIVE_WEATHER_FILE)

    if "district_key" not in df.columns and "district" in df.columns:
        df = df.rename(columns={"district": "district_key"})

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    return df.dropna(subset=["date"])


@st.cache_data(ttl=3600)
def load_historical_weather():

    if not HISTORICAL_WEATHER_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(HISTORICAL_WEATHER_FILE)

    if "district_key" not in df.columns and "district" in df.columns:
        df = df.rename(columns={"district": "district_key"})

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    return df.dropna(subset=["date"])


@st.cache_data(ttl=900)
def load_ml_predictions():

    if not ML_PREDICTIONS_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(ML_PREDICTIONS_FILE)

    df["forecast_origin"] = pd.to_datetime(
        df["forecast_origin"],
        errors="coerce"
    )

    df["forecast_date"] = pd.to_datetime(
        df["forecast_date"],
        errors="coerce"
    )

    return df.dropna(
        subset=["forecast_origin", "forecast_date"]
    )


# ==================================================
# 4. LIVE WEATHER UPDATE BUTTON
# ==================================================

col1, col2 = st.columns([1, 3])

with col1:

    if st.button(
        "🔄 Update Live Weather",
        use_container_width=True
    ):

        try:

            with st.spinner(
                "Updating weather for all 25 districts..."
            ):

                update_live_weather()

            load_live_weather.clear()

            st.success("Live weather updated successfully!")

            st.rerun()

        except Exception as error:

            st.error(
                f"Weather update failed: {error}"
            )


# ==================================================
# 5. LOAD DATASETS
# ==================================================

try:

    live_df = load_live_weather()

    historical_df = load_historical_weather()

    ml_df = load_ml_predictions()

except Exception as error:

    st.error(
        f"Could not load dashboard data: {error}"
    )

    st.stop()


# ==================================================
# SECTION A: TODAY'S WEATHER
# ==================================================

st.header(
    f"1. Today's Weather — {today.strftime('%d %B %Y')}"
)

st.caption(
    "Source: Open-Meteo Forecast API. "
    "These values represent today's API weather estimates, "
    "not verified ground observations."
)

if live_df.empty:

    st.warning(
        "Today's weather data is unavailable. "
        "Please update live weather."
    )

else:

    today_df = live_df[
        live_df["date"].dt.date == today
    ].copy()

    if today_df.empty:

        st.warning(
            f"No weather data available for "
            f"{today.strftime('%d %B %Y')}."
        )

    else:

        # ------------------------------------------
        # DISTRICT SELECTION
        # ------------------------------------------

        district_options = [
            "All Districts"
        ] + sorted(
            today_df["district_key"].dropna().unique()
        )

        selected_today_district = st.selectbox(
            "Select District - Today's Weather",
            district_options,
            key="today_district"
        )

        if selected_today_district != "All Districts":

            today_df = today_df[
                today_df["district_key"]
                == selected_today_district
            ].copy()

        # ------------------------------------------
        # WEATHER SUMMARY
        # ------------------------------------------

        required_live_columns = [
            "district_key",
            "precipitation_sum",
            "temperature_2m_mean"
        ]

        missing = [
            col for col in required_live_columns
            if col not in today_df.columns
        ]

        if missing:

            st.error(
                f"Missing live weather columns: {missing}"
            )

        else:

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Districts",
                today_df["district_key"].nunique()
            )

            c2.metric(
                "Average Temperature",
                f"{today_df['temperature_2m_mean'].mean():.1f} °C"
            )

            c3.metric(
                "Average Rainfall",
                f"{today_df['precipitation_sum'].mean():.1f} mm"
            )

            c4.metric(
                "Maximum Rainfall",
                f"{today_df['precipitation_sum'].max():.1f} mm"
            )

            # --------------------------------------
            # RAINFALL CHART
            # --------------------------------------

            st.subheader(
                "🌧️ Today's Rainfall by District"
            )

            rainfall_fig = px.bar(
                today_df.sort_values(
                    "precipitation_sum",
                    ascending=False
                ),
                x="district_key",
                y="precipitation_sum",
                color="precipitation_sum",
                color_continuous_scale="Teal",
                labels={
                    "district_key": "District",
                    "precipitation_sum": "Rainfall (mm)"
                }
            )

            rainfall_fig.update_layout(
                xaxis_tickangle=-45,
                template="plotly_white"
            )

            st.plotly_chart(
                rainfall_fig,
                use_container_width=True
            )

            # --------------------------------------
            # TEMPERATURE CHART
            # --------------------------------------

            st.subheader(
                "🌡️ Today's Mean Temperature"
            )

            temperature_fig = px.bar(
                today_df.sort_values(
                    "temperature_2m_mean",
                    ascending=False
                ),
                x="district_key",
                y="temperature_2m_mean",
                color="temperature_2m_mean",
                color_continuous_scale="Oranges",
                labels={
                    "district_key": "District",
                    "temperature_2m_mean": "Temperature (°C)"
                }
            )

            temperature_fig.update_layout(
                xaxis_tickangle=-45,
                template="plotly_white"
            )

            st.plotly_chart(
                temperature_fig,
                use_container_width=True
            )

            # --------------------------------------
            # TODAY'S WEATHER TABLE
            # --------------------------------------

            st.subheader(
                "Today's District Weather Records"
            )

            st.dataframe(
                today_df.sort_values(
                    "precipitation_sum",
                    ascending=False
                ),
                use_container_width=True,
                hide_index=True
            )


# ==================================================
# SECTION B: HISTORICAL WEATHER PATTERNS
# ==================================================

st.divider()

st.header("2. Historical Weather Patterns")

st.caption(
    "Historical weather data from the combined ERA5 dataset."
)

if historical_df.empty:

    st.warning(
        "Historical ERA5 dataset was not found."
    )

else:

    required_history_columns = [
        "district_key",
        "date",
        "precipitation_sum",
        "temperature_2m_mean"
    ]

    missing = [
        col for col in required_history_columns
        if col not in historical_df.columns
    ]

    if missing:

        st.error(
            f"Missing historical columns: {missing}"
        )

    else:

        historical_df = historical_df.sort_values(
            "date"
        )

        st.write(
            f"ERA5 coverage: "
            f"{historical_df['date'].min():%d %B %Y} "
            f"to {historical_df['date'].max():%d %B %Y}"
        )

        st.write(
            f"Total districts: "
            f"{historical_df['district_key'].nunique()}"
        )

        # ------------------------------------------
        # DISTRICT SELECTION
        # ------------------------------------------

        history_districts = [
            "All Districts"
        ] + sorted(
            historical_df["district_key"].dropna().unique()
        )

        selected_history_district = st.selectbox(
            "Select District - Historical Weather",
            history_districts,
            key="history_district"
        )

        if selected_history_district == "All Districts":

            history_view = historical_df.copy()

        else:

            history_view = historical_df[
                historical_df["district_key"]
                == selected_history_district
            ].copy()

        # ------------------------------------------
        # MONTHLY AGGREGATION
        # ------------------------------------------

        monthly_history = (
            history_view.assign(
                year_month=history_view["date"].dt.to_period("M")
            )
            .groupby("year_month", as_index=False)
            .agg(
                average_rainfall=(
                    "precipitation_sum",
                    "mean"
                ),
                average_temperature=(
                    "temperature_2m_mean",
                    "mean"
                )
            )
        )

        monthly_history["date"] = (
            monthly_history["year_month"]
            .dt.to_timestamp()
        )

        # ------------------------------------------
        # MONTHLY RAINFALL
        # ------------------------------------------

        st.subheader(
            "🌧️ Historical Monthly Rainfall Pattern"
        )

        monthly_rainfall_fig = px.line(
            monthly_history,
            x="date",
            y="average_rainfall",
            markers=True,
            labels={
                "date": "Month",
                "average_rainfall": "Average Daily Rainfall (mm)"
            }
        )

        monthly_rainfall_fig.update_layout(
            template="plotly_white"
        )

        st.plotly_chart(
            monthly_rainfall_fig,
            use_container_width=True
        )

        # ------------------------------------------
        # MONTHLY TEMPERATURE
        # ------------------------------------------

        st.subheader(
            "🌡️ Historical Monthly Temperature Pattern"
        )

        monthly_temperature_fig = px.line(
            monthly_history,
            x="date",
            y="average_temperature",
            markers=True,
            labels={
                "date": "Month",
                "average_temperature": "Mean Temperature (°C)"
            }
        )

        monthly_temperature_fig.update_layout(
            template="plotly_white"
        )

        st.plotly_chart(
            monthly_temperature_fig,
            use_container_width=True
        )

        # ------------------------------------------
        # RECENT 90-DAY TREND
        # ------------------------------------------

        st.subheader(
            "📈 Recent Historical Weather Trend"
        )

        daily_history = (
            history_view.groupby("date", as_index=False)
            .agg(
                average_rainfall=(
                    "precipitation_sum",
                    "mean"
                ),
                average_temperature=(
                    "temperature_2m_mean",
                    "mean"
                )
            )
            .sort_values("date")
        )

        recent_history = daily_history.tail(90)

        recent_fig = px.line(
            recent_history,
            x="date",
            y="average_rainfall",
            markers=True,
            labels={
                "date": "Date",
                "average_rainfall": "Average Rainfall (mm)"
            },
            title="Daily Rainfall - Last 90 Available Days"
        )

        recent_fig.update_layout(
            template="plotly_white"
        )

        st.plotly_chart(
            recent_fig,
            use_container_width=True
        )


# ==================================================
# SECTION C: RISKWEAVE ML PREDICTIONS
# ==================================================

st.divider()

st.header("3. RiskWeave ML Predictions")

st.caption(
    "Rainfall and mean temperature predictions generated "
    "by the four trained RiskWeave machine-learning models."
)

if ml_df.empty:

    st.warning(
        "No saved ML prediction records found."
    )

else:

    # ----------------------------------------------
    # CHOOSE PREDICTION PERIOD
    # ----------------------------------------------

    has_upcoming_predictions = (
        ml_df["forecast_date"].dt.date > today
    ).any()

    default_prediction_index = (
        0 if has_upcoming_predictions else 1
    )

    prediction_period = st.radio(
        "Prediction Records",
        [
            "Upcoming Predictions",
            "Previous Predictions"
        ],
        index=default_prediction_index,
        horizontal=True,
        key="ml_prediction_period"
    )

    if prediction_period == "Upcoming Predictions":

        display_ml = ml_df[
            ml_df["forecast_date"].dt.date > today
        ].copy()

    else:

        display_ml = ml_df[
            ml_df["forecast_date"].dt.date <= today
        ].copy()

    if display_ml.empty:

        st.warning(
            "No prediction records available for this selection."
        )

    else:

        # ------------------------------------------
        # DISTRICT SELECTION
        # ------------------------------------------

        ml_districts = [
            "All Districts"
        ] + sorted(
            display_ml["district"].dropna().unique()
        )

        selected_ml_district = st.selectbox(
            "Select District - ML Predictions",
            ml_districts,
            key="ml_district"
        )

        if selected_ml_district != "All Districts":

            display_ml = display_ml[
                display_ml["district"]
                == selected_ml_district
            ].copy()

        # ------------------------------------------
        # FORECAST HORIZON SELECTION
        # ------------------------------------------

        available_horizons = sorted(
            display_ml["horizon_days"].unique()
        )

        selected_horizon = st.radio(
            "Select Prediction Horizon",
            available_horizons,
            format_func=lambda x: (
                "1-Day Prediction"
                if x == 1
                else "7-Day Prediction"
                if x == 7
                else f"{x}-Day Prediction"
            ),
            horizontal=True,
            key="ml_horizon"
        )

        selected_ml = display_ml[
            display_ml["horizon_days"]
            == selected_horizon
        ].copy()

        # ------------------------------------------
        # FORECAST INFORMATION
        # ------------------------------------------

        forecast_origin = (
            selected_ml["forecast_origin"].iloc[0]
        )

        forecast_date = (
            selected_ml["forecast_date"].iloc[0]
        )

        st.info(
            f"Forecast origin: "
            f"{forecast_origin:%d %B %Y} | "
            f"Target date: {forecast_date:%d %B %Y}"
        )

        # ------------------------------------------
        # SEPARATE TARGETS
        # ------------------------------------------

        rainfall_ml = selected_ml[
            selected_ml["target"]
            == "precipitation_sum"
        ].copy()

        temperature_ml = selected_ml[
            selected_ml["target"]
            == "temperature_2m_mean"
        ].copy()

        # ------------------------------------------
        # PREDICTION SUMMARY
        # ------------------------------------------

        col1, col2 = st.columns(2)

        if not rainfall_ml.empty:

            col1.metric(
                "Average Predicted Rainfall",
                f"{rainfall_ml['predicted_value'].mean():.2f} mm"
            )

        if not temperature_ml.empty:

            col2.metric(
                "Average Predicted Temperature",
                f"{temperature_ml['predicted_value'].mean():.2f} °C"
            )

        # ------------------------------------------
        # RAINFALL PREDICTIONS
        # ------------------------------------------

        st.subheader(
            "🌧️ ML-Predicted Rainfall"
        )

        if not rainfall_ml.empty:

            if selected_ml_district == "All Districts":

                ml_rainfall_fig = px.bar(
                    rainfall_ml.sort_values(
                        "predicted_value",
                        ascending=False
                    ),
                    x="district",
                    y="predicted_value",
                    color="predicted_value",
                    color_continuous_scale="Teal",
                    labels={
                        "district": "District",
                        "predicted_value": "Predicted Rainfall (mm)"
                    }
                )

                ml_rainfall_fig.update_layout(
                    xaxis_tickangle=-45,
                    template="plotly_white"
                )

                st.plotly_chart(
                    ml_rainfall_fig,
                    use_container_width=True
                )

            st.dataframe(
                rainfall_ml[
                    [
                        "district",
                        "predicted_value",
                        "forecast_date"
                    ]
                ].rename(
                    columns={
                        "district": "District",
                        "predicted_value": "Predicted Rainfall (mm)",
                        "forecast_date": "Forecast Date"
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "Rainfall predictions are unavailable "
                "for this selection."
            )

        # ------------------------------------------
        # TEMPERATURE PREDICTIONS
        # ------------------------------------------

        st.subheader(
            "🌡️ ML-Predicted Mean Temperature"
        )

        if not temperature_ml.empty:

            if selected_ml_district == "All Districts":

                ml_temperature_fig = px.bar(
                    temperature_ml.sort_values(
                        "predicted_value",
                        ascending=False
                    ),
                    x="district",
                    y="predicted_value",
                    color="predicted_value",
                    color_continuous_scale="Oranges",
                    labels={
                        "district": "District",
                        "predicted_value": "Predicted Temperature (°C)"
                    }
                )

                ml_temperature_fig.update_layout(
                    xaxis_tickangle=-45,
                    template="plotly_white"
                )

                st.plotly_chart(
                    ml_temperature_fig,
                    use_container_width=True
                )

            st.dataframe(
                temperature_ml[
                    [
                        "district",
                        "predicted_value",
                        "forecast_date"
                    ]
                ].rename(
                    columns={
                        "district": "District",
                        "predicted_value": "Predicted Temperature (°C)",
                        "forecast_date": "Forecast Date"
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info(
                "Temperature predictions are unavailable "
                "for this selection."
            )

        # ------------------------------------------
        # MODEL DETAILS
        # ------------------------------------------

        with st.expander("View model information"):

            st.dataframe(
                selected_ml[
                    [
                        "district",
                        "target",
                        "horizon_days",
                        "model_name",
                        "predicted_value",
                        "forecast_origin",
                        "forecast_date"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )


# ==================================================
# 7. DATA SOURCE INFORMATION
# ==================================================

st.divider()

st.caption(
    "Today's weather: Open-Meteo Forecast API | "
    "Historical patterns: ERA5 | "
    "ML predictions: RiskWeave trained models | "
    "Coverage: 25 Sri Lankan districts."
)
