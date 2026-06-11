import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, page_header

d = load_all()
scope = page_header("Plan vs actual", d.profiles)
st.caption("Planned contribution per category (target × budget) vs what you actually invested. Negative shortfall = under-invested.")

years = compute.available_years(d.budget, d.contributions)
if not years:
    st.info("No data yet — add budget rows and contributions on the Update Data page.")
    st.stop()

contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
default = contrib_years[-1] if contrib_years else years[-1]
year = st.selectbox("Year", years, index=years.index(default))

if scope is None:
    pva = compute.household_plan_vs_actual(d.profiles, d.budget, d.targets, d.contributions, year)
    goal_rows = d.goals[d.goals["year"] == year]
else:
    profile = next(p for p in d.profiles if p.key == scope)
    pva = compute.plan_vs_actual(profile, d.budget, d.targets, d.contributions, year)
    goal_rows = d.goals[(d.goals["year"] == year) & (d.goals["profile"] == scope)]

if pva.empty:
    st.info("No plan for this scope/year yet.")
    st.stop()

cols = st.columns(2)
cols[0].metric("Goal achieved", f"{compute.pct_goal_achieved(pva):.1f}%")
if not goal_rows.empty:
    cols[1].metric("Emergency-fund goal", inr(goal_rows["emergency_fund_goal"].sum()))

st.dataframe(
    pva,
    column_config={
        "category": "Category",
        "expected": st.column_config.NumberColumn("Planned (₹)", format="%.0f"),
        "actual": st.column_config.NumberColumn("Actual (₹)", format="%.0f"),
        "shortfall": st.column_config.NumberColumn("Shortfall / surplus (₹)", format="%.0f"),
    },
    hide_index=True,
    width="stretch",
)

st.subheader("Drawdown — shortfall by category")
st.bar_chart(pva.set_index("category")["shortfall"], color="#2b2b2b")
