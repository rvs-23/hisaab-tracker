import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import GRAYS, TEAL, inr, load_all, page_header

d = load_all()
scope = page_header("CBSE Finances", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

CURRENT_YEAR = dt.date.today().year
years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page — everything derives from it.")
    st.stop()

# Where do we stand this year?
pva_all = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, CURRENT_YEAR)
cols = st.columns(3 + (len(selected) if len(selected) > 1 else 0))
cols[0].metric(f"Goal achieved · {CURRENT_YEAR}", f"{compute.pct_goal_achieved(pva_all):.0f}%")
cols[1].metric("Invested so far", inr(pva_all["actual"].sum()))
cols[2].metric("Planned for the year", inr(pva_all["expected"].sum()))
if len(selected) > 1:
    for i, p in enumerate(selected):
        pva = compute.plan_vs_actual(p, d.income, d.targets, d.contributions, CURRENT_YEAR)
        cols[3 + i].metric(p.name, f"{compute.pct_goal_achieved(pva):.0f}%" if not pva.empty else "—")

goals = d.goals[(d.goals["year"] == CURRENT_YEAR) & (d.goals["profile"].isin(scope))]
if not goals.empty:
    st.caption(f"Emergency-fund goal {CURRENT_YEAR}: {inr(goals['emergency_fund_goal'].sum())}")

st.subheader("Cumulative investment")
series = {}
for p in selected:
    bs = compute.budget_series(p, d.income)
    if not bs.empty:
        series[p.name] = bs.set_index("year")["cumulative_invested"]
chart = pd.DataFrame(series)
if len(series) > 1:
    chart["Combined"] = chart.sum(axis=1)
    colors = GRAYS[: len(series)] + [TEAL]
else:
    colors = TEAL
st.line_chart(chart, color=colors)
st.caption("Includes projected years (current + 3 at assumed growth). Details on the Budget page.")
