import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    MULBERRY, inr, inr_short, load_all, page_header, pretty_category,
)

ON_TRACK = 75  # % of goal that counts a year as "on track"

d = load_all()
scope = page_header("Dashboard", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page — everything derives from it.")
    st.stop()

# Headline on the latest year that actually has contributions (meaningful), not a
# possibly-empty calendar year.
contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
year = contrib_years[-1] if contrib_years else years[-1]


def stats(profiles):
    pva = compute.household_plan_vs_actual(profiles, d.income, d.targets, d.contributions, year)
    target = pva["expected"].sum()
    invested = pva["actual"].sum()
    income_yr = invest_yr = 0.0
    for p in profiles:
        bs = compute.budget_series(p, d.income)
        row = bs[bs["year"] == year]
        if not row.empty:
            income_yr += row.iloc[0]["total_income"]
            invest_yr += row.iloc[0]["investment"]
    return {
        "target": target,
        "invested": invested,
        "remaining": max(target - invested, 0.0),
        "progress": compute.pct_goal_achieved(pva) if not pva.empty else 0.0,
        "rate": 100 * invest_yr / income_yr if income_yr else 0.0,
    }


# Goal progress — one card per selected person, plus Household when 2+ are picked.
st.subheader(
    f"Goal progress · {year}",
    help="Share of this year's investment target that's actually been invested so far "
    "(actual contributions ÷ planned). 100% = exactly on plan.",
)
entities = [(p.name, [p]) for p in selected]
if len(selected) > 1:
    entities.append(("Household", selected))

cols = st.columns(len(entities))
for col, (name, profs) in zip(cols, entities):
    s = stats(profs)
    col.metric(name, f"{s['progress']:.0f}%")
    col.caption(f"{inr_short(s['invested'])} of {inr_short(s['target'])}")

# Years on track + the category we're most behind on, for the selection.
hh_year = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
on_track = sum(
    1
    for cy in contrib_years
    if compute.pct_goal_achieved(
        compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, cy)
    )
    >= ON_TRACK
)
bits = [f"On track: **{on_track} of {len(contrib_years)}** years ≥ {ON_TRACK}% of goal"]
if not hh_year.empty:
    worst = hh_year.loc[hh_year["shortfall"].idxmin()]
    if worst["shortfall"] < 0:
        bits.append(f"most behind: **{pretty_category(worst['category'])}** ({inr_short(worst['shortfall'])})")
st.caption(" · ".join(bits))

# This year's actionable numbers, for the whole selection.
agg = stats(selected)
invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()
ai = compute.annual_income(d.income)
ai = ai[ai["profile"].isin(scope)]


def income_for(yr):
    return ai[ai["year"] == yr][["salary", "bonus", "other"]].sum().sum()


inc_now, inc_prev = income_for(year), income_for(year - 1)
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else None

st.subheader(f"This year · {year}")
m = st.columns(4)
m[0].metric("Income", inr_short(inc_now), delta=yoy, delta_color="off")
m[1].metric("Target amount", inr_short(agg["target"]), help=f"Planned investment for {year} (target % × budget).")
m[2].metric("Still to invest", inr_short(agg["remaining"]), help="Target minus what's gone in so far.")
m[3].metric("Monthly target", inr_short(agg["target"] / 12), help="Target amount ÷ 12 — see the Monthly Plan page for the per-instrument split.")
st.caption(
    f"Investing **{agg['rate']:.0f}%** of income this year · "
    f"**{inr(invested_to_date)}** invested to date across all years."
)

# Cumulative planned investment over time.
st.subheader(
    "Cumulative planned investment",
    help="Running total of how much the budget says to invest, year over year "
    "(including projected years). This is the plan — not market value or portfolio worth.",
)
series = {}
for p in selected:
    bs = compute.budget_series(p, d.income)
    if not bs.empty:
        series[p.name] = bs.set_index("year")["cumulative_invested"]
chart = pd.DataFrame(series)
if len(series) > 1:
    chart["Combined"] = chart.sum(axis=1)
st.line_chart(chart, color=MULBERRY if chart.shape[1] == 1 else None)

goals = d.goals[(d.goals["year"] == year) & (d.goals["profile"].isin(scope))]
if not goals.empty:
    st.caption(f"Emergency-fund goal ({year}): {inr(goals['emergency_fund_goal'].sum())}")
