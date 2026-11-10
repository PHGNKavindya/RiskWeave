
from pathlib import Path
import subprocess
import sys

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ============================================================
# PROJECT DATA PATHS
# ============================================================

LIVE_FILE = PROJECT_ROOT / "data/raw/weather_live/live_weather_forecasts.csv"

API_FORECAST_FILE = (
    PROJECT_ROOT / "data/raw/weather_live/dashboard_weather_forecasts.csv"
)

HISTORICAL_FILE = (
    PROJECT_ROOT / "data/processed/weather_era5_combined_2006_2026.csv"
)

OPERATIONAL_FILE = (
    PROJECT_ROOT / "data/processed/weather_operational_combined_2006_2026.csv"
)

ML_FILE = (
    PROJECT_ROOT
    / "outputs/weather_forecasting/operational/latest_ml_weather_predictions.csv"
)


# ============================================================
# DAILY WEATHER UPDATE
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
def run_daily_update(local_date_key: str):
    """
    Shared daily update for both forecasting pages.

    Streamlit caches this workflow across pages so switching
    between rainfall and temperature does not repeat API calls
    on the same local date.
    """

    from weather_forecasting.live_weather import update_live_weather

    update_live_weather()

    scripts = [
        PROJECT_ROOT / "create_operational_dataset.py",
        PROJECT_ROOT / "run_operational_weather_predictions.py",
    ]

    for script in scripts:

        if not script.exists():
            raise FileNotFoundError(
                f"Required project script not found: {script}"
            )

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:

            details = result.stderr or result.stdout

            raise RuntimeError(
                f"{script.name} failed "
                f"(exit code {result.returncode}).\n{details}"
            )

    return {
        "updated": True,
        "date": local_date_key,
    }


# ============================================================
# CSV LOADING
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def _read_csv_cached(path_string: str, modified_time: float):

    path = Path(path_string)

    if not path.exists():
        return pd.DataFrame()

    return pd.read_csv(path)


def load_csv(path: Path):

    if not path.exists():
        return pd.DataFrame()

    return _read_csv_cached(
        str(path),
        path.stat().st_mtime,
    )


def load_weather_data():

    live = load_csv(LIVE_FILE)
    api_forecast = load_csv(API_FORECAST_FILE)
    historical = load_csv(HISTORICAL_FILE)
    operational = load_csv(OPERATIONAL_FILE)
    predictions = load_csv(ML_FILE)

    weather_frames = (
        live,
        api_forecast,
        historical,
        operational,
    )

    for frame in weather_frames:

        if not frame.empty:

            if (
                "district_key" not in frame.columns
                and "district" in frame.columns
            ):
                frame.rename(
                    columns={"district": "district_key"},
                    inplace=True,
                )

            if "date" in frame.columns:

                frame["date"] = pd.to_datetime(
                    frame["date"],
                    errors="coerce",
                )

    if not predictions.empty:

        for column in ("forecast_origin", "forecast_date"):

            if column in predictions.columns:

                predictions[column] = pd.to_datetime(
                    predictions[column],
                    errors="coerce",
                )

    return (
        live,
        api_forecast,
        historical,
        operational,
        predictions,
    )


# ============================================================
# DATE AND UPDATE STATUS
# ============================================================

def get_today():

    return pd.Timestamp.now(
        tz="Asia/Colombo"
    ).date()


def show_update_status():

    today = get_today()

    try:

        with st.spinner(
            "Checking and updating live weather for all 25 districts..."
        ):

            run_daily_update(today.isoformat())

        st.success(
            f"Weather data and ML predictions are up to date "
            f"for {today:%d %B %Y}."
        )

    except Exception as exc:

        st.error(
            f"Automatic weather update failed: {exc}"
        )

        st.info(
            "The dashboard will attempt to display the latest files "
            "already saved. Check the terminal output and update scripts "
            "if this error continues."
        )


def show_manual_update_button():

    if st.button(
        "🔄 Update Live Weather Now",
        width="content",
    ):

        run_daily_update.clear()
        _read_csv_cached.clear()

        st.rerun()


# ============================================================
# DISTRICT FILTER
# ============================================================

def select_district(frame, key):

    if frame.empty or "district_key" not in frame.columns:
        return frame

    choices = ["All Districts"] + sorted(
        frame["district_key"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    selected = st.selectbox(
        "Select district",
        choices,
        key=key,
    )

    if selected != "All Districts":

        return frame[
            frame["district_key"].astype(str) == selected
        ].copy()

    return frame.copy()


# ============================================================
# HISTORICAL DATA PREPARATION
# ============================================================

def prepare_historical_data(
    historical,
    required_columns,
    value_column,
):
    """
    Prepare historical observations for charting.

    - Converts dates safely.
    - Converts the selected weather variable to numeric.
    - Removes invalid dates and missing values.
    - Sorts observations chronologically.

    This function does not modify the original historical dataset.
    """

    if historical.empty:
        return pd.DataFrame()

    required = set(required_columns)

    if not required.issubset(historical.columns):
        return pd.DataFrame()

    view = historical.copy()

    view["date"] = pd.to_datetime(
        view["date"],
        errors="coerce",
    )

    view[value_column] = pd.to_numeric(
        view[value_column],
        errors="coerce",
    )

    view = view.dropna(
        subset=["date", value_column, "district_key"]
    )

    view = view.sort_values("date")

    return view


def create_monthly_summary(view, value_column, output_column):
    """
    Calculate monthly average weather values.

    Includes every available month in the selected dataset.
    New historical records are automatically included after
    the source dataset is refreshed.
    """

    if view.empty:
        return pd.DataFrame()

    monthly = (
        view.assign(
            month=view["date"].dt.to_period("M")
        )
        .groupby("month", as_index=False)
        .agg(
            **{
                output_column: (value_column, "mean")
            }
        )
    )

    monthly["date"] = monthly["month"].dt.to_timestamp()

    return monthly.sort_values("date")


def create_recent_90_day_summary(
    view,
    value_column,
    output_column,
):
    """
    Calculate the recent 90-calendar-day trend.

    The latest date is taken from the latest valid observation
    in the selected dataset.

    The period includes the latest observation date and the
    preceding 89 calendar days.
    """

    if view.empty:
        return pd.DataFrame()

    latest_date = view["date"].max().normalize()

    start_date = latest_date - pd.Timedelta(days=89)

    recent_data = view[
        (view["date"] >= start_date)
        & (view["date"] < latest_date + pd.Timedelta(days=1))
    ].copy()

    if recent_data.empty:
        return pd.DataFrame()

    daily = (
        recent_data.groupby("date", as_index=False)
        .agg(
            **{
                output_column: (value_column, "mean")
            }
        )
        .sort_values("date")
    )

    return daily



# ============================================================
# HISTORICAL RAINFALL CHARTS
# ============================================================

def show_historical_rainfall(
    historical,
    district_key,
    recent_data=None,
):
    import plotly.express as px

    st.subheader("Historical Monthly Rainfall Pattern")

    required = {
        "date",
        "precipitation_sum",
        "district_key",
    }

    if historical.empty or not required.issubset(historical.columns):
        st.warning(
            "Historical ERA5 rainfall data is unavailable "
            "or missing required columns."
        )
        return

    # ERA5 dataset: used for the historical monthly chart.
    view = select_district(historical, district_key)

    view = prepare_historical_data(
        view,
        required,
        "precipitation_sum",
    )

    if view.empty:
        st.warning("No valid historical rainfall records are available.")
        return

    monthly = create_monthly_summary(
        view,
        "precipitation_sum",
        "average_daily_rainfall",
    )

    if not monthly.empty:
        fig = px.line(
            monthly,
            x="date",
            y="average_daily_rainfall",
            markers=True,
            labels={
                "date": "Month",
                "average_daily_rainfall": "Average daily rainfall (mm)",
            },
        )

        fig.update_layout(
            template="plotly_white",
            xaxis_title="Month",
            yaxis_title="Average daily rainfall (mm)",
        )

        st.plotly_chart(fig, width="stretch")

    # Operational dataset: used for the latest 90-day chart.
    st.subheader("Recent 90-Day Rainfall Trend")

    if recent_data is None or recent_data.empty:
        st.warning(
            "Recent operational rainfall data is unavailable. "
            "The latest 90-day trend cannot be displayed."
        )
        return

    recent_required = {
        "date",
        "precipitation_sum",
        "district_key",
    }

    if not recent_required.issubset(recent_data.columns):
        st.warning(
            "Operational rainfall data is missing required columns."
        )
        return

    # Reuse the district selection made for the monthly chart.
    selected_districts = view["district_key"].astype(str).unique()

    recent_view = recent_data[
        recent_data["district_key"].astype(str).isin(selected_districts)
    ].copy()

    recent_view = prepare_historical_data(
        recent_view,
        recent_required,
        "precipitation_sum",
    )

    daily = create_recent_90_day_summary(
        recent_view,
        "precipitation_sum",
        "average_rainfall",
    )

    if daily.empty:
        st.warning("Recent rainfall observations are unavailable.")
        return

    st.caption(
        f"Operational weather data | "
        f"{daily['date'].min():%d %B %Y} to "
        f"{daily['date'].max():%d %B %Y}"
    )

    recent_fig = px.line(
        daily,
        x="date",
        y="average_rainfall",
        markers=True,
        labels={
            "date": "Date",
            "average_rainfall": "Average rainfall (mm)",
        },
    )

    recent_fig.update_layout(
        template="plotly_white",
        xaxis_title="Date",
        yaxis_title="Average rainfall (mm)",
    )

    st.plotly_chart(recent_fig, width="stretch")


# ============================================================
# HISTORICAL TEMPERATURE CHARTS
# ============================================================

def show_historical_temperature(
    historical,
    district_key,
    recent_data=None,
):
    import plotly.express as px

    st.subheader("Historical Monthly Temperature Pattern")

    required = {
        "date",
        "temperature_2m_mean",
        "district_key",
    }

    if historical.empty or not required.issubset(historical.columns):
        st.warning(
            "Historical ERA5 temperature data is unavailable "
            "or missing required columns."
        )
        return

    # ERA5 dataset: used for the historical monthly chart.
    view = select_district(historical, district_key)

    view = prepare_historical_data(
        view,
        required,
        "temperature_2m_mean",
    )

    if view.empty:
        st.warning(
            "No valid historical temperature records are available."
        )
        return

    monthly = create_monthly_summary(
        view,
        "temperature_2m_mean",
        "average_temperature",
    )

    if not monthly.empty:
        fig = px.line(
            monthly,
            x="date",
            y="average_temperature",
            markers=True,
            labels={
                "date": "Month",
                "average_temperature": "Mean temperature (°C)",
            },
        )

        fig.update_layout(
            template="plotly_white",
            xaxis_title="Month",
            yaxis_title="Mean temperature (°C)",
        )

        st.plotly_chart(fig, width="stretch")

    # Operational dataset: used for the latest 90-day chart.
    st.subheader("Recent 90-Day Temperature Trend")

    if recent_data is None or recent_data.empty:
        st.warning(
            "Recent operational temperature data is unavailable. "
            "The latest 90-day trend cannot be displayed."
        )
        return

    recent_required = {
        "date",
        "temperature_2m_mean",
        "district_key",
    }

    if not recent_required.issubset(recent_data.columns):
        st.warning(
            "Operational temperature data is missing required columns."
        )
        return

    # Reuse the district selection made for the monthly chart.
    selected_districts = view["district_key"].astype(str).unique()

    recent_view = recent_data[
        recent_data["district_key"].astype(str).isin(selected_districts)
    ].copy()

    recent_view = prepare_historical_data(
        recent_view,
        recent_required,
        "temperature_2m_mean",
    )

    daily = create_recent_90_day_summary(
        recent_view,
        "temperature_2m_mean",
        "average_temperature",
    )

    if daily.empty:
        st.warning("Recent temperature observations are unavailable.")
        return

    st.caption(
        f"Operational weather data | "
        f"{daily['date'].min():%d %B %Y} to "
        f"{daily['date'].max():%d %B %Y}"
    )

    recent_fig = px.line(
        daily,
        x="date",
        y="average_temperature",
        markers=True,
        labels={
            "date": "Date",
            "average_temperature": "Mean temperature (°C)",
        },
    )

    recent_fig.update_layout(
        template="plotly_white",
        xaxis_title="Date",
        yaxis_title="Mean temperature (°C)",
    )

    st.plotly_chart(recent_fig, width="stretch")

