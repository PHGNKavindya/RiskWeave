
import streamlit as st
from streamlit_folium import st_folium

from src.dengue_forecasting.dengue_map import (
    create_homepage_map
)

st.set_page_config(
    page_title="RiskWeave Map Test",
    layout="wide"
)

st.title("RiskWeave – Interactive Dengue Map")

try:
    dengue_map = create_homepage_map()

    st_folium(
        dengue_map,
        width=None,
        height=600,
        returned_objects=[]
    )

except Exception as error:
    st.error(f"Map error: {error}")
