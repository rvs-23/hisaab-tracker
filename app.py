from pathlib import Path

import streamlit as st

st.set_page_config(page_title="CBSE Finances", page_icon=":material/savings:", layout="wide")
st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")

st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("views/plan_vs_actual.py", title="Plan vs Actual", icon=":material/track_changes:"),
        st.Page("views/budget_projection.py", title="Budget & Projection", icon=":material/trending_up:"),
        st.Page("views/income.py", title="Income", icon=":material/payments:"),
    ]
).run()
