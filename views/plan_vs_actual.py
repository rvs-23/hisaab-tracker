import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import edit_grid, inr, load_all, page_header

d = load_all()
scope = page_header("Plan vs actual", d.profiles)
st.caption("Planned contribution per category (target × budget) vs what you actually invested. Negative shortfall = under-invested.")

_keys = [p.key for p in d.profiles]
_cats = d.config.categories
edit_grid(
    d.contributions,
    {
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "profile": st.column_config.SelectboxColumn("Person", options=_keys, required=True),
        "category": st.column_config.SelectboxColumn("Category", options=_cats, required=True),
        "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
        "notes": "Notes",
    },
    lambda df: storage.validate_contributions(df, d.config, d.profiles),
    storage.save_contributions,
    d.root, key="contrib_editor", label="contributions", sort=["year", "profile", "category"],
)
edit_grid(
    d.targets,
    {
        "profile": st.column_config.SelectboxColumn("Person", options=_keys, required=True),
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "tier": st.column_config.SelectboxColumn("Tier", options=["short_term", "long_term"], required=True),
        "category": st.column_config.SelectboxColumn("Category", options=_cats, required=True),
        "pct": st.column_config.NumberColumn("Percent", required=True),
    },
    lambda df: storage.validate_targets(df, d.config, d.profiles),
    storage.save_targets,
    d.root, key="targets_editor", label="targets (per-year overrides)",
)
edit_grid(
    d.goals,
    {
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "profile": st.column_config.SelectboxColumn("Person", options=_keys, required=True),
        "emergency_fund_goal": st.column_config.NumberColumn("Emergency-fund goal (₹)", required=True),
    },
    lambda df: storage.validate_goals(df, d.profiles),
    storage.save_goals,
    d.root, key="goals_editor", label="emergency-fund goals", sort=["year", "profile"],
)

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
