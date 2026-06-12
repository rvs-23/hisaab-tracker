import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, page_header

d = load_all()
scope = page_header("CBSE Finances", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("No data yet — add income and contributions on the Update Data page.")
    st.stop()

# Headline on the latest year that actually has contributions recorded.
contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
year = contrib_years[-1] if contrib_years else years[-1]

st.caption(f"Investment plan vs actual — {year}")

combined = len(selected) > 1
cols = st.columns(len(selected) + (1 if combined else 0))
i = 0
if combined:
    house = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
    cols[0].metric("Combined — goal achieved", f"{compute.pct_goal_achieved(house):.0f}%")
    i = 1
for p in selected:
    pva = compute.plan_vs_actual(p, d.income, d.targets, d.contributions, year)
    val = f"{compute.pct_goal_achieved(pva):.0f}%" if not pva.empty else "—"
    cols[i].metric(f"{p.name} — goal achieved", val)
    i += 1

goals = d.goals[(d.goals["year"] == year) & (d.goals["profile"].isin(scope))]
if not goals.empty:
    st.metric(f"Emergency-fund goal ({year})", inr(goals["emergency_fund_goal"].sum()))

st.subheader("Planned cumulative investment")
series = {}
for p in selected:
    proj = compute.projection(p, d.income)
    if not proj.empty:
        series[p.name] = proj.set_index("year")["cumulative_invested"]
chart = pd.DataFrame(series)
if combined and not chart.empty:
    chart["Combined"] = chart.sum(axis=1)
st.line_chart(chart, color="#2b2b2b" if chart.shape[1] == 1 else None)
