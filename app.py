
import streamlit as st

st.set_page_config(
    page_title="RiskWeave | Climate & Dengue Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------- CUSTOM DESIGN ----------------

st.markdown("""
<style>
    .stApp {
        background-color: #F5F8FA;
    }

    [data-testid="stSidebar"] {
        background-color: #102A43;
    }

    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    .main-title {
        font-size: 38px;
        font-weight: 800;
        color: #123047;
        margin-bottom: 5px;
    }

    .subtitle {
        font-size: 16px;
        color: #627D98;
        margin-bottom: 25px;
    }

    .section-title {
        color: #123047;
        font-size: 23px;
        font-weight: 700;
        margin-top: 20px;
    }

    .module-card {
        background: white;
        padding: 22px;
        border-radius: 12px;
        border: 1px solid #E1E8ED;
        min-height: 155px;
        margin-bottom: 12px;
    }

    .module-card h3 {
        color: #123047;
        font-size: 19px;
    }

    .module-card p {
        color: #627D98;
        font-size: 14px;
    }

    .status {
        color: #087F5B;
        font-weight: 700;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("# 🌿 RiskWeave")
    st.caption("Climate & Dengue Intelligence")
    st.divider()

    st.markdown("### SRI LANKA")
    st.markdown("Climate-informed public health intelligence")

    st.divider()
    st.caption("PROJECT VERSION 1.0")


# ---------------- HOME PAGE ----------------

st.markdown(
    '<div class="main-title">RiskWeave Intelligence Platform</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Climate-informed dengue risk forecasting and inspection planning '
    'for Sri Lanka.'
    '</div>',
    unsafe_allow_html=True
)

# Welcome section
st.info(
    "Welcome to RiskWeave. Explore climate conditions, "
    "dengue risk forecasts and inspection-planning insights "
    "through the navigation pages."
)

# Summary cards
st.markdown('<div class="section-title">Platform Overview</div>',
            unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("District Coverage", "25", "Sri Lankan districts")

with col2:
    st.metric("Weather Forecast Horizons", "1 & 7 Days")

with col3:
    st.metric("Platform Modules", "5", "Integrated components")


# Module cards
st.markdown('<div class="section-title">Platform Modules</div>',
            unsafe_allow_html=True)

row1 = st.columns(2)

with row1[0]:
    st.markdown("""
    <div class="module-card">
        <h3>🌦️ Weather Forecasting</h3>
        <p>Daily rainfall and temperature forecasts
        for Sri Lankan districts.</p>
        <span class="status">● WEATHER MODULE</span>
    </div>
    """, unsafe_allow_html=True)

with row1[1]:
    st.markdown("""
    <div class="module-card">
        <h3>🦟 Dengue Risk Prediction</h3>
        <p>Forecast dengue risk using historical
        dengue and environmental information.</p>
        <span class="status">● DEVELOPMENT</span>
    </div>
    """, unsafe_allow_html=True)

row2 = st.columns(2)

with row2[0]:
    st.markdown("""
    <div class="module-card">
        <h3>🌱 Environmental Anomaly Detection</h3>
        <p>Identify unusual rainfall, temperature and
        relative humidity patterns using historical
        district-level weather baselines.</p>
        <span class="status">● COMPLETED</span>
    </div>
    """, unsafe_allow_html=True)

with row2[1]:
    st.markdown("""
    <div class="module-card">
        <h3>📍 Inspection Priority</h3>
        <p>Identify locations that may require
        priority field inspections.</p>
        <span class="status">● DEVELOPMENT</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="module-card">
    <h3>🗺️ Route Optimization</h3>
    <p>Support efficient inspection route planning
    using geographic and priority information.</p>
    <span class="status">● DEVELOPMENT</span>
</div>
""", unsafe_allow_html=True)


# Footer
st.divider()
st.caption(
    "RiskWeave | Climate-informed Dengue Risk Forecasting "
    "and Inspection Planning | Sri Lanka"
)
