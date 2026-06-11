import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import edit_grid, inr, load_all, page_header

d = load_all()
scope = page_header("Budget & projection", d.profiles)

edit_grid(
    d.budget,
    {
        "profile": st.column_config.SelectboxColumn("Person", options=[p.key for p in d.profiles], required=True),
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "starting_salary": st.column_config.NumberColumn("Starting salary (₹)"),
        "job_change": st.column_config.SelectboxColumn("Job change?", options=["No", "Yes"]),
        "ending_salary": st.column_config.NumberColumn("Gross salary (₹)", required=True),
        "monthly_needs": st.column_config.NumberColumn("Needs /mo (₹)", required=True),
        "monthly_wants": st.column_config.NumberColumn("Wants /mo (₹)", required=True),
        "monthly_investment": st.column_config.NumberColumn("Invest /mo (₹)", required=True),
    },
    lambda df: storage.validate_budget(df, d.profiles),
    storage.save_budget,
    d.root, key="budget_editor", label="budget", sort=["profile", "year"],
)

# Per-person by nature — if "Household" is selected, fall back to the first person.
profile = next((p for p in d.profiles if p.key == scope), None) or d.profiles[0]
if scope is None:
    st.caption(f"Per-person view — showing {profile.name}. Pick a person in the sidebar to switch.")

rows = d.budget[d.budget["profile"] == profile.key].sort_values("year")
if rows.empty:
    st.info(f"No budget rows for {profile.name} yet — add them on the Update Data page.")
    st.stop()

latest = rows.iloc[-1]
pct = compute.split_pct(latest)
st.subheader(f"Monthly budget split — {int(latest['year'])}")
cols = st.columns(4)
cols[0].metric("Salary / mo", inr(latest["ending_salary"] / 12))
cols[1].metric(f"Needs ({pct['needs']:.0f}%)", inr(latest["monthly_needs"]))
cols[2].metric(f"Wants ({pct['wants']:.0f}%)", inr(latest["monthly_wants"]))
cols[3].metric(f"Investment ({pct['investment']:.0f}%)", inr(latest["monthly_investment"]))

st.subheader("Projection")
st.caption("Cumulative invested is contributions-only (no return assumptions), straight from the budget plan.")
proj = compute.projection(profile, d.budget)
st.line_chart(proj.set_index("year")["cumulative_invested"], color="#2b2b2b")
st.dataframe(
    proj,
    column_config={
        "year": st.column_config.NumberColumn("Year", format="%d"),
        "age": "Age",
        "ending_salary": st.column_config.NumberColumn("Gross salary (₹)", format="%.0f"),
        "monthly_needs": st.column_config.NumberColumn("Needs /mo (₹)", format="%.0f"),
        "monthly_wants": st.column_config.NumberColumn("Wants /mo (₹)", format="%.0f"),
        "monthly_investment": st.column_config.NumberColumn("Invest /mo (₹)", format="%.0f"),
        "invested_this_year": st.column_config.NumberColumn("Invested in year (₹)", format="%.0f"),
        "cumulative_invested": st.column_config.NumberColumn("Cumulative (₹)", format="%.0f"),
    },
    hide_index=True,
    width="stretch",
)
