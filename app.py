from pathlib import Path

import streamlit as st

from config import HOUSEHOLD_KEY
from ui import active_profile_key, inject_theme

st.set_page_config(page_title="Personal Finances Tracker", page_icon=":material/savings:", layout="wide")
st.logo(str(Path(__file__).parent / "logo.svg"), size="large")
inject_theme()  # Inter font + the CSS variables our HTML uses (light theme only)

dashboard = st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True)
if active_profile_key() == HOUSEHOLD_KEY:
    # The combined view only reads: income, budget and actuals are edited per person.
    pages = [dashboard, st.Page("views/house_fund.py", title="House fund", icon=":material/home:")]
else:
    # Nav reads as the money pipeline: in -> split (allocation is edited on
    # Budget, under the monthly split) -> record actuals.
    pages = [
        dashboard,
        st.Page("views/income.py", title="Income", icon=":material/payments:"),
        st.Page("views/budget_projection.py", title="Budget", icon=":material/call_split:"),
        st.Page("views/actuals.py", title="Actuals", icon=":material/track_changes:"),
    ]
st.navigation(pages).run()
