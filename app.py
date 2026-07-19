from pathlib import Path

import streamlit as st

from ui import inject_theme

st.set_page_config(page_title="Personal Finances Tracker", page_icon=":material/savings:", layout="wide")
st.logo(str(Path(__file__).parent / "logo.svg"), size="large")
inject_theme()  # Inter font + the CSS variables our HTML uses (light theme only)

# Nav reads as the money pipeline: in -> split -> record actuals (allocation is
# edited inline on Actuals, not its own stop on the pipeline).
st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("views/income.py", title="Income", icon=":material/payments:"),
        st.Page("views/budget_projection.py", title="Budget", icon=":material/call_split:"),
        st.Page("views/actuals.py", title="Actuals", icon=":material/track_changes:"),
    ]
).run()
