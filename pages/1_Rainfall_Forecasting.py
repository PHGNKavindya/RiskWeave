
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from weather_forecasting.dashboard_common import (
    get_today,
    load_weather_data,
    select_district,
    show_historical_rainfall,
    show_manual_update_button,
    show_update_status,
)

st.set_page_config(
    page_title="Rainfall Forecasting | RiskWeave",
    page_icon="🌧️",
    layout="wide",
)

st.title("🌧️ RiskWeave — Rainfall Forecasting")
st.caption(
    "Machine-learning rainfall predictions and historical rainfall "
    "patterns for 25 districts of Sri Lanka."
)
st.divider()

today = get_today()

show_update_status()
show_manual_update_button()

live, api_forecast, historical, operational, predictions = load_weather_data()

# ============================================================
# 1. TODAY'S ML-PREDICTED RAINFALL
# ============================================================

st.header(f"1. Today's ML-Predicted Rainfall — {today:%d %B %Y}")

st.caption(
    "RiskWeave 1-day rainfall model. The forecast origin should be yesterday "
    "and the target date should be today. Values are model predictions, not observations."
)

if predictions.empty:
    st.warning(
        "No saved ML predictions were found. "
        "Check the operational prediction workflow."
    )

else:
    required = {
        "target",
        "horizon_days",
        "forecast_origin",
        "forecast_date",
        "district",
        "predicted_value",
        "model_name",
    }

    missing = required - set(predictions.columns)

    if missing:
        st.error(f"The ML prediction file is missing columns: {sorted(missing)}")

    else:
        rain_predictions = predictions[
            (predictions["target"] == "precipitation_sum")
            & (predictions["horizon_days"] == 1)
            & (predictions["forecast_date"].dt.date == today)
        ].copy()

        if rain_predictions.empty:
            st.warning(
                "Today's 1-day rainfall predictions are not present in the saved file. "
                "Confirm that the operational forecast origin is yesterday "
                "and rerun the prediction workflow."
            )

        else:
            rain_predictions = rain_predictions.rename(
                columns={"district": "district_key"}
            )

            rain_predictions = select_district(
                rain_predictions,
                "rain_today_ml_district",
            )

            # Summary metrics
            c1, c2 = st.columns(2)

            c1.metric(
                "Districts predicted",
                rain_predictions["district_key"].nunique(),
            )

            c2.metric(
                "Average predicted rainfall",
                f"{rain_predictions['predicted_value'].mean():.2f} mm",
            )

            # District-level rainfall chart
            if rain_predictions["district_key"].nunique() > 1:

                fig = px.bar(
                    rain_predictions.sort_values(
                        "predicted_value",
                        ascending=False,
                    ),
                    x="district_key",
                    y="predicted_value",
                    color="predicted_value",
                    color_continuous_scale="Teal",
                    labels={
                        "district_key": "District",
                        "predicted_value": "Predicted rainfall (mm)",
                    },
                )

                fig.update_layout(
                    template="plotly_white",
                    xaxis_tickangle=-45,
                )

                st.plotly_chart(fig, width="stretch")

            # Prediction table
            st.dataframe(
                rain_predictions[
                    [
                        "district_key",
                        "forecast_origin",
                        "forecast_date",
                        "predicted_value",
                        "model_name",
                    ]
                ].rename(
                    columns={
                        "district_key": "District",
                        "forecast_origin": "Forecast origin",
                        "forecast_date": "Target date",
                        "predicted_value": "Predicted rainfall (mm)",
                        "model_name": "Model",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

# ============================================================
# 2. SEVEN-DAY-AHEAD ML RAINFALL PREDICTION
# ============================================================

st.divider()

st.header("2. Seven-Day-Ahead ML Rainfall Prediction")

st.caption(
    "RiskWeave 7-day model. This is one prediction for the date "
    "seven days after the forecast origin; it is not a separate "
    "prediction for each of the next seven calendar days."
)

if (
    not predictions.empty
    and {
        "target",
        "horizon_days",
        "forecast_date",
        "district",
        "predicted_value",
    }.issubset(predictions.columns)
):

    seven_day = predictions[
        (predictions["target"] == "precipitation_sum")
        & (predictions["horizon_days"] == 7)
        & (predictions["forecast_date"].dt.date > today)
    ].copy()

    if seven_day.empty:
        st.info(
            "No upcoming 7-day-ahead rainfall prediction "
            "is available in the saved file."
        )

    else:
        seven_day = seven_day.rename(
            columns={"district": "district_key"}
        )

        target_dates = sorted(
            seven_day["forecast_date"].dt.date.unique()
        )

        chosen_date = st.selectbox(
            "7-day prediction target date",
            target_dates,
            format_func=lambda value: value.strftime("%d %B %Y"),
            key="rain_7day_target_date",
        )

        seven_day = seven_day[
            seven_day["forecast_date"].dt.date == chosen_date
        ].copy()

        seven_day = select_district(
            seven_day,
            "rain_7day_ml_district",
        )

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Target date",
            chosen_date.strftime("%d %B %Y"),
        )

        c2.metric(
            "Average predicted rainfall",
            f"{seven_day['predicted_value'].mean():.2f} mm",
        )

        c3.metric(
            "Districts predicted",
            seven_day["district_key"].nunique(),
        )

        if seven_day["district_key"].nunique() > 1:

            fig = px.bar(
                seven_day.sort_values(
                    "predicted_value",
                    ascending=False,
                ),
                x="district_key",
                y="predicted_value",
                color="predicted_value",
                color_continuous_scale="Teal",
                labels={
                    "district_key": "District",
                    "predicted_value": "Predicted rainfall (mm)",
                },
            )

            fig.update_layout(
                template="plotly_white",
                xaxis_tickangle=-45,
            )

            st.plotly_chart(fig, width="stretch")

        st.dataframe(
            seven_day[
                [
                    "district_key",
                    "forecast_origin",
                    "forecast_date",
                    "predicted_value",
                    "model_name",
                ]
            ].rename(
                columns={
                    "district_key": "District",
                    "forecast_origin": "Forecast origin",
                    "forecast_date": "Target date",
                    "predicted_value": "Predicted rainfall (mm)",
                    "model_name": "Model",
                }
            ),
            width="stretch",
            hide_index=True,
        )

else:
    st.info(
        "The saved ML prediction file is unavailable "
        "or does not contain the required columns."
    )

# ============================================================
# 3. HISTORICAL RAINFALL PATTERNS
# ============================================================

st.divider()

st.header("3. Historical Rainfall Patterns — ERA5")

if historical.empty:
    st.warning("Historical ERA5 dataset was not found.")

else:
    if {"date", "district_key"}.issubset(historical.columns):

        st.write(
            f"ERA5 coverage: {historical['date'].min():%d %B %Y} to "
            f"{historical['date'].max():%d %B %Y} | "
            f"Districts: {historical['district_key'].nunique()}"
        )

    show_historical_rainfall(
        historical,
        "history_rain_district",
        recent_data=operational,
    )

st.divider()

st.caption(
    "Historical source: ERA5 | Operational weather inputs: Open-Meteo APIs | "
    "Displayed forecasts: RiskWeave trained machine-learning models. "
    "Rainfall model performance is subject to the limitations documented "
    "in the project evaluation."
)
