from pathlib import Path

import streamlit as st

from finance_tracker.ui import inject_theme, sidebar_dark_toggle

st.set_page_config(page_title="CBSE Finances", page_icon=":material/savings:", layout="wide")
st.logo(str(Path(__file__).parent / "assets" / "logo.svg"), size="large")
inject_theme()
sidebar_dark_toggle()  # one global dark-mode toggle at the top of the sidebar

# Nav reads as the money pipeline: in -> split -> destination -> monthly action -> verdict.
st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("views/income.py", title="Income", icon=":material/payments:"),
        st.Page("views/budget_projection.py", title="Budget", icon=":material/call_split:"),
        st.Page("views/target.py", title="Target", icon=":material/flag:"),
        st.Page("views/monthly_plan.py", title="Monthly Plan", icon=":material/event_repeat:"),
        st.Page("views/plan_vs_actual.py", title="Plan vs Actual", icon=":material/track_changes:"),
    ]
).run()
