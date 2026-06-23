from pathlib import Path

import streamlit as st

from ui import inject_theme

st.set_page_config(page_title="CBSE Finances", page_icon=":material/savings:", layout="wide")
st.logo(str(Path(__file__).parent / "logo.svg"), size="large")
inject_theme()  # font + theme-aware variables; dark mode via ☰ → Settings → Theme

# Nav reads as the money pipeline: in -> split -> allocate -> record actuals.
st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("views/income.py", title="Income", icon=":material/payments:"),
        st.Page("views/budget_projection.py", title="Budget", icon=":material/call_split:"),
        st.Page("views/allocation.py", title="Allocation", icon=":material/donut_small:"),
        st.Page("views/actuals.py", title="Actuals", icon=":material/track_changes:"),
    ]
).run()
