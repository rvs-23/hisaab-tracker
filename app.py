import streamlit as st

st.set_page_config(page_title="Hisaab", page_icon="₹", layout="wide")

st.navigation(
    [
        st.Page("views/dashboard.py", title="Dashboard", icon="🏠", default=True),
        st.Page("views/allocation.py", title="Allocation", icon="🥧"),
        st.Page("views/plan_vs_actual.py", title="Plan vs Actual", icon="🎯"),
        st.Page("views/budget_projection.py", title="Budget & Projection", icon="📈"),
        st.Page("views/income.py", title="Income", icon="💰"),
        st.Page("views/edit_data.py", title="Update Data", icon="✏️"),
    ]
).run()
