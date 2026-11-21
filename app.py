
import streamlit as st
from home import render_home

st.set_page_config(
    page_title="RiskWeave | Climate & Dengue Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.markdown("# 🌿 RiskWeave")
    st.caption("Climate & Dengue Intelligence")
    st.divider()

    st.markdown("### SRI LANKA")
    st.markdown("Climate-informed public health intelligence")

    st.divider()
    st.caption("PROJECT VERSION 1.0")

render_home()
