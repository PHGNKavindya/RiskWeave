
import streamlit as st
import textwrap

from streamlit_folium import st_folium
from src.dengue_forecasting.dengue_map import create_homepage_map


# ============================================================
# 1. HTML RENDERING HELPER
# ============================================================

def render_html(content):

    st.html(textwrap.dedent(content))


# ============================================================
# 2. HOMEPAGE
# ============================================================

def render_home():

    # --------------------------------------------------------
    # CUSTOM CSS
    # --------------------------------------------------------

    render_html("""
    <style>

    .stApp {
        background:
            radial-gradient(circle at center, #10364d, #07172b 75%);
        color: #eafaff;
    }

    .block-container {
        max-width: 1600px;
        padding-top: 1rem;
        padding-bottom: 1rem;
    }

    /* HEADER */

    .rw-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px 22px;
        background: linear-gradient(100deg, #0b2944, #10465c);
        border: 1px solid #247e91;
        border-radius: 12px;
        box-shadow: 0 0 20px #087e9070;
    }

    .rw-logo {
        font-size: 25px;
        font-weight: 900;
        letter-spacing: 3px;
        color: white;
    }

    .rw-logo span {
        color: #46e0cf;
    }

    .rw-status {
        color: #61e6c4;
        font-size: 11px;
        border: 1px solid #329e8b;
        padding: 7px 12px;
        border-radius: 20px;
    }

    .rw-title {
        text-align: center;
        font-size: 27px;
        font-weight: 800;
        letter-spacing: 2px;
        color: #eaffff;
        margin-top: 22px;
    }

    .rw-subtitle {
        text-align: center;
        color: #91b9ce;
        font-size: 12px;
        letter-spacing: 1px;
        margin-bottom: 20px;
    }

    /* METRICS */

    .rw-metrics {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin-bottom: 16px;
    }

    .rw-metric {
        background: linear-gradient(140deg, #123c57, #0a253e);
        border: 1px solid #286d86;
        border-radius: 10px;
        padding: 13px;
        box-shadow: inset 0 0 15px #28a6b522;
    }

    .rw-label {
        color: #8dbdd0;
        font-size: 10px;
        letter-spacing: 1px;
    }

    .rw-value {
        color: white;
        font-size: 25px;
        font-weight: 800;
        margin-top: 4px;
    }

    .rw-note {
        color: #55dcca;
        font-size: 10px;
    }

    /* PANELS */

    .rw-panel {
        background: rgba(8, 37, 61, .96);
        border: 1px solid #26849a;
        border-radius: 10px;
        padding: 13px;
        margin-bottom: 12px;
        box-shadow: 0 0 17px #087e9040;
    }

    .rw-panel-title {
        color: #65e1d7;
        font-size: 12px;
        font-weight: 800;
        border-bottom: 1px solid #28647a;
        padding-bottom: 8px;
        margin-bottom: 8px;
    }

    .rw-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #ffffff12;
        color: #a8c7d8;
        font-size: 11px;
        gap: 5px;
    }

    .rw-row strong {
        color: white;
    }

    .rw-description {
        color: #8db3c7;
        font-size: 10px;
        line-height: 1.6;
        margin-top: 9px;
    }

    /* MAP PANEL */

    .rw-map-heading {
        color: #65e1d7;
        font-size: 13px;
        font-weight: 800;
        padding: 10px 12px;
        background: #0b2944;
        border: 1px solid #26849a;
        border-radius: 9px 9px 0 0;
    }

    .rw-map-caption {
        color: #91b9ce;
        font-size: 10px;
        padding: 8px 12px;
        background: #0b2944;
        border: 1px solid #26849a;
        border-top: none;
        border-radius: 0 0 9px 9px;
    }

    /* BOTTOM PANELS */

    .rw-bottom {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 11px;
        margin-top: 13px;
    }

    .rw-bottom-panel {
        background: #0c2d48;
        border: 1px solid #286c85;
        border-radius: 10px;
        padding: 14px;
        min-height: 90px;
    }

    .rw-bottom-title {
        color: #62ddd2;
        font-size: 11px;
        font-weight: bold;
    }

    .rw-bottom-text {
        color: #a2c0d0;
        font-size: 10px;
        margin-top: 8px;
        line-height: 1.6;
    }

    .rw-footer {
        text-align: center;
        color: #668fa4;
        font-size: 9px;
        margin-top: 20px;
    }

    /* STREAMLIT MAP CONTAINER */

    div[data-testid="stVerticalBlock"] {
        gap: 0.6rem;
    }

    @media(max-width: 800px) {

        .rw-metrics {
            grid-template-columns: repeat(2, 1fr);
        }

        .rw-bottom {
            grid-template-columns: 1fr;
        }

        .rw-title {
            font-size: 21px;
        }

        .rw-header {
            flex-direction: column;
            gap: 10px;
        }
    }

    </style>
    """)

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    render_html("""
    <div class="rw-header">
        <div>
            <div class="rw-logo">
                RISK<span>WEAVE</span> LANKA
            </div>

            <div style="color:#91b9ce;font-size:10px;letter-spacing:2px">
                CLIMATE & DENGUE INTELLIGENCE
            </div>
        </div>

        <div class="rw-status">
            ● RESEARCH MONITORING PLATFORM
        </div>
    </div>

    <div class="rw-title">
        DENGUE INTELLIGENCE COMMAND CENTRE
    </div>

    <div class="rw-subtitle">
        SEE THE RISK · PREDICT THE CHANGE · PLAN THE RESPONSE
    </div>
    """)

    # --------------------------------------------------------
    # TOP METRICS
    # --------------------------------------------------------

    render_html("""
    <div class="rw-metrics">

        <div class="rw-metric">
            <div class="rw-label">TEMPERATURE</div>
            <div class="rw-value">-- °C</div>
            <div class="rw-note">Weather monitoring</div>
        </div>

        <div class="rw-metric">
            <div class="rw-label">RAINFALL</div>
            <div class="rw-value">-- mm</div>
            <div class="rw-note">Precipitation monitoring</div>
        </div>

        <div class="rw-metric">
            <div class="rw-label">DENGUE CASES</div>
            <div class="rw-value">--</div>
            <div class="rw-note">Latest reported cases</div>
        </div>

        <div class="rw-metric">
            <div class="rw-label">FORECAST HORIZON</div>
            <div class="rw-value">7 Days</div>
            <div class="rw-note">Forecast target horizon</div>
        </div>

    </div>
    """)

    # --------------------------------------------------------
    # MAIN COMMAND CENTRE
    # --------------------------------------------------------

    left_col, map_col, right_col = st.columns(
        [0.95, 2.1, 0.95],
        gap="small"
    )

    # ========================================================
    # LEFT PANELS
    # ========================================================

    with left_col:

        render_html("""
        <div class="rw-panel">

            <div class="rw-panel-title">
                🦟 DENGUE SURVEILLANCE
            </div>

            <div class="rw-row">
                <span>Weekly cases</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>District</span>
                <strong>All areas</strong>
            </div>

            <div class="rw-row">
                <span>Reporting week</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Source</span>
                <strong>NDCU</strong>
            </div>

        </div>

        <div class="rw-panel">

            <div class="rw-panel-title">
                🌱 ENVIRONMENTAL ANOMALIES
            </div>

            <div class="rw-row">
                <span>Rainfall anomaly</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Temperature anomaly</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Humidity anomaly</span>
                <strong>--</strong>
            </div>

        </div>

        <div class="rw-panel">

            <div class="rw-panel-title">
                📍 GEOGRAPHIC COVERAGE
            </div>

            <div class="rw-row">
                <span>Target geography</span>
                <strong>District / MOH*</strong>
            </div>

            <div class="rw-description">
                Geographic resolution depends on verified
                historical data and available boundaries.
            </div>

        </div>
        """)

    # ========================================================
    # CENTRAL INTERACTIVE MAP
    # ========================================================

    with map_col:

        render_html("""
        <div class="rw-map-heading">
            🗺️ SRI LANKA — DENGUE FORECAST MAP
        </div>
        """)

        try:

            dengue_map = create_homepage_map()

            st_folium(
                dengue_map,
                width=None,
                height=510,
                returned_objects=[]
            )

        except Exception as error:

            st.error(
                f"Unable to load dengue map: {error}"
            )

            st.info(
                "Please check the dengue prediction "
                "and geographical data files."
            )

        render_html("""
        <div class="rw-map-caption">
            District colours represent model-predicted dengue cases.
            Select or hover over a district for further information.
        </div>
        """)

    # ========================================================
    # RIGHT PANELS
    # ========================================================

    with right_col:

        render_html("""
        <div class="rw-panel">

            <div class="rw-panel-title">
                🌦️ WEATHER INTELLIGENCE
            </div>

            <div class="rw-row">
                <span>Mean temperature</span>
                <strong>-- °C</strong>
            </div>

            <div class="rw-row">
                <span>Daily rainfall</span>
                <strong>-- mm</strong>
            </div>

            <div class="rw-row">
                <span>Relative humidity</span>
                <strong>-- %</strong>
            </div>

            <div class="rw-row">
                <span>Last update</span>
                <strong>--</strong>
            </div>

        </div>

        <div class="rw-panel">

            <div class="rw-panel-title">
                🧠 FORECAST INTELLIGENCE
            </div>

            <div class="rw-row">
                <span>Next-week cases</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Forecast model</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Uncertainty</span>
                <strong>--</strong>
            </div>

        </div>

        <div class="rw-panel">

            <div class="rw-panel-title">
                🚩 INSPECTION OPERATIONS
            </div>

            <div class="rw-row">
                <span>Priority areas</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Suggested visits</span>
                <strong>--</strong>
            </div>

            <div class="rw-row">
                <span>Route distance</span>
                <strong>-- km</strong>
            </div>

        </div>
        """)

    # --------------------------------------------------------
    # BOTTOM INFORMATION
    # --------------------------------------------------------

    render_html("""
    <div class="rw-bottom">

        <div class="rw-bottom-panel">

            <div class="rw-bottom-title">
                🌧️ WEATHER & CLIMATE TRENDS
            </div>

            <div class="rw-bottom-text">
                Temperature and rainfall trends from
                the processed weather dataset.
            </div>

        </div>

        <div class="rw-bottom-panel">

            <div class="rw-bottom-title">
                📊 MODEL PERFORMANCE
            </div>

            <div class="rw-bottom-text">
                Temporal evaluation, MAE, RMSE
                and prediction uncertainty.
            </div>

        </div>

        <div class="rw-bottom-panel">

            <div class="rw-bottom-title">
                ⚙️ DATA & SYSTEM STATUS
            </div>

            <div class="rw-bottom-text">
                Dengue data updates, weather API status
                and data-quality monitoring.
            </div>

        </div>

    </div>

    <div class="rw-footer">
        RISKWEAVE LANKA · CLIMATE-INFORMED DENGUE
        FORECASTING & INSPECTION PLANNING
    </div>
    """)
