
from pathlib import Path

import pandas as pd
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="RiskWeave | Environmental Analysis",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Environmental Anomaly Detection")
st.caption(
    "District-level analysis of unusual rainfall, "
    "temperature and relative humidity patterns."
)

st.info(
    "Environmental anomalies represent unusual weather "
    "conditions relative to historical district-level "
    "baselines. They are not direct dengue risk predictions."
)


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent

ANOMALY_DIR = (
    PROJECT_DIR
    / "data"
    / "processed"
    / "environmental_anomalies"
)


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

@st.cache_data
def load_anomaly_data():

    daily = pd.read_csv(
        ANOMALY_DIR / "weather_anomaly_daily_2026.csv",
        parse_dates=["date"]
    )

    district = pd.read_csv(
        ANOMALY_DIR / "district_anomaly_summary_2026.csv"
    )

    monthly = pd.read_csv(
        ANOMALY_DIR / "monthly_anomaly_summary_2026.csv"
    )

    return daily, district, monthly


try:

    daily_df, district_df, monthly_df = load_anomaly_data()

    st.success("Environmental anomaly datasets loaded successfully.")

except FileNotFoundError as error:

    st.error(f"Required anomaly dataset not found: {error}")

    st.stop()

except Exception as error:

    st.error(f"Error loading environmental anomaly data: {error}")

    st.stop()


# --------------------------------------------------
# DATASET INFORMATION
# --------------------------------------------------

st.subheader("Dataset Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Districts Covered",
        daily_df["district"].nunique()
    )

with col2:
    st.metric(
        "Daily Records",
        f"{len(daily_df):,}"
    )

with col3:
    st.metric(
        "Districts in Summary",
        district_df["district"].nunique()
    )


st.write("**Daily observation period:**")

st.write(
    f"{daily_df['date'].min().date()} "
    f"to {daily_df['date'].max().date()}"
)


# --------------------------------------------------
# DATA PREVIEW
# --------------------------------------------------

with st.expander("View daily anomaly records"):

    st.dataframe(
        daily_df,
        use_container_width=True,
        hide_index=True
    )


with st.expander("View district anomaly summary"):

    st.dataframe(
        district_df,
        use_container_width=True,
        hide_index=True
    )


with st.expander("View monthly anomaly summary"):

    st.dataframe(
        monthly_df,
        use_container_width=True,
        hide_index=True
    )
