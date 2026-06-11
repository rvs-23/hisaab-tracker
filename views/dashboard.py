import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, sidebar_scope

d = load_all()
scope = sidebar_scope(d.profiles)

st.title("Hisaab")

years = compute.available_years(d.budget, d.contributions)
if not years:
    st.info("No data yet — add budget rows and contributions on the Update Data page.")
    st.stop()

# Headline on the latest year that actually has contributions recorded.
contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
year = contrib_years[-1] if contrib_years else years[-1]


def pva_for(key):
    if key is None:
        return compute.household_plan_vs_actual(d.profiles, d.budget, d.contributions, year)
    profile = next(p for p in d.profiles if p.key == key)
    return compute.plan_vs_actual(profile, d.budget, d.contributions, year)


st.caption(f"Investment plan vs actual — {year}")
cols = st.columns(len(d.profiles) + 1)
house = pva_for(None)
cols[0].metric("Household — goal achieved", f"{compute.pct_goal_achieved(house):.0f}%")
for col, p in zip(cols[1:], d.profiles):
    pva = pva_for(p.key)
    val = f"{compute.pct_goal_achieved(pva):.0f}%" if not pva.empty else "—"
    col.metric(f"{p.name} — goal achieved", val)

# Emergency-fund goal for the scope/year.
goals = d.goals[d.goals["year"] == year]
if scope is not None:
    goals = goals[goals["profile"] == scope]
if not goals.empty:
    st.metric(f"Emergency-fund goal ({year})", inr(goals["emergency_fund_goal"].sum()))

# Cumulative-invested trajectory from the budget plan.
st.subheader("Planned cumulative investment")
if scope is None:
    frames = [
        compute.projection(p, d.budget).set_index("year")["cumulative_invested"]
        for p in d.profiles
        if not compute.projection(p, d.budget).empty
    ]
    series = pd.concat(frames, axis=1).sum(axis=1) if frames else pd.Series(dtype=float)
else:
    profile = next(p for p in d.profiles if p.key == scope)
    proj = compute.projection(profile, d.budget)
    series = proj.set_index("year")["cumulative_invested"] if not proj.empty else pd.Series(dtype=float)
st.line_chart(series, color="#2b2b2b")

st.caption(f"data folder: {d.root}")
