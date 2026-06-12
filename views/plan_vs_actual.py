import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import MULBERRY, TEAL, inr, load_all, page_header

d = load_all()
scope = page_header("Plan vs Actual", d.profiles)
st.caption("Did we invest what the plan said? Planned (mulberry) vs actual (teal) per category. Negative shortfall = under-invested.")

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("No data yet — add income first.")
    st.stop()

contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
default = contrib_years[-1] if contrib_years else years[-1]
year = st.selectbox("Year", years, index=years.index(default))

selected = [p for p in d.profiles if p.key in scope]
pva = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
goal_rows = d.goals[(d.goals["year"] == year) & (d.goals["profile"].isin(scope))]

if pva.empty:
    st.info("No plan for this selection/year yet.")
    st.stop()

cols = st.columns(2)
cols[0].metric("Goal achieved", f"{compute.pct_goal_achieved(pva):.1f}%")
if not goal_rows.empty:
    cols[1].metric("Emergency-fund goal", inr(goal_rows["emergency_fund_goal"].sum()))

st.dataframe(
    pva.sort_values("expected", ascending=False),
    column_config={
        "category": "Category",
        "expected": st.column_config.NumberColumn("Planned (₹)", format="%.0f"),
        "actual": st.column_config.NumberColumn("Actual (₹)", format="%.0f"),
        "shortfall": st.column_config.NumberColumn("Shortfall / surplus (₹)", format="%.0f"),
    },
    hide_index=True, width="stretch",
)

chart = pva.set_index("category")[["expected", "actual"]].rename(
    columns={"expected": "Planned", "actual": "Actual"}
)
st.bar_chart(chart, color=[MULBERRY, TEAL], horizontal=True)

# --- edit-in-place: the actuals this page is built on -----------------------

st.divider()
st.subheader("Record actual contributions")
edited = st.data_editor(
    d.contributions.sort_values(["year", "profile", "category"]).reset_index(drop=True),
    num_rows="dynamic", hide_index=True, width="stretch", key="contrib_editor",
    column_config={
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "profile": st.column_config.SelectboxColumn("Person", options=[p.key for p in d.profiles], required=True),
        "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
        "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
        "notes": "Notes",
    },
)
if st.button("Save contributions", type="primary"):
    try:
        storage.validate_contributions(edited, d.config, d.profiles)
        storage.save_contributions(d.root, edited)
        st.success("Saved.")
        st.rerun()
    except Exception as exc:
        st.error(f"Not saved: {exc}")

st.subheader("Emergency-fund goals")
edited_goals = st.data_editor(
    d.goals.sort_values(["year", "profile"]).reset_index(drop=True),
    num_rows="dynamic", hide_index=True, width="stretch", key="goals_editor",
    column_config={
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "profile": st.column_config.SelectboxColumn("Person", options=[p.key for p in d.profiles], required=True),
        "emergency_fund_goal": st.column_config.NumberColumn("Goal (₹)", required=True),
    },
)
if st.button("Save goals", type="primary"):
    try:
        storage.validate_goals(edited_goals, d.profiles)
        storage.save_goals(d.root, edited_goals)
        st.success("Saved.")
        st.rerun()
    except Exception as exc:
        st.error(f"Not saved: {exc}")
