import streamlit as st

st.set_page_config(page_title="Hisaab", page_icon="₹", layout="wide")

st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
        st.Page("views/allocation.py", title="Allocation", icon=":material/donut_small:"),
        st.Page("views/plan_vs_actual.py", title="Plan vs Actual", icon=":material/track_changes:"),
        st.Page("views/budget_projection.py", title="Budget & Projection", icon=":material/trending_up:"),
        st.Page("views/income.py", title="Income", icon=":material/payments:"),
        st.Page("views/edit_data.py", title="Update Data", icon=":material/edit:"),
    ]
).run()
