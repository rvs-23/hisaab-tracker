import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, sidebar_scope

root, config, profiles, holdings, income = load_all()
scope = sidebar_scope(profiles)

st.title("Budget & projection")

# Per-person by nature — if "Household" is selected, fall back to the first person.
profile = next((p for p in profiles if p.key == scope), None) or profiles[0]
if scope is None:
    st.caption(f"Per-person view — showing {profile.name}. Pick a person in the sidebar to switch.")

st.subheader("Monthly budget split")
split = compute.budget_split(profile)
cols = st.columns(4)
cols[0].metric("Salary", inr(profile.monthly_salary))
cols[1].metric(f"Needs ({profile.split.needs:.0f}%)", inr(split["needs"]))
cols[2].metric(f"Wants ({profile.split.wants:.0f}%)", inr(split["wants"]))
cols[3].metric(f"Investment ({profile.split.investment:.0f}%)", inr(split["investment"]))

st.subheader(f"{profile.projection_years}-year projection")
st.caption(
    f"Salary grows {profile.salary_increment_pct}% per year; cumulative invested is "
    "contributions only (no return assumptions), as in the spreadsheet model."
)
proj = compute.projection(profile)
st.line_chart(proj.set_index("year")["cumulative_invested"], color="#2b2b2b")
st.dataframe(
    proj,
    column_config={
        "year": st.column_config.NumberColumn("Year", format="%d"),
        "age": "Age",
        "monthly_salary": st.column_config.NumberColumn("Salary /mo (₹)", format="%.0f"),
        "monthly_investment": st.column_config.NumberColumn("Invest /mo (₹)", format="%.0f"),
        "invested_this_year": st.column_config.NumberColumn("Invested in year (₹)", format="%.0f"),
        "cumulative_invested": st.column_config.NumberColumn("Cumulative (₹)", format="%.0f"),
    },
    hide_index=True,
    width="stretch",
)
