import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    INK, MULBERRY, TEAL, inr, inr_short, load_all, page_header, pretty_category,
)

ON_TRACK = 75  # % of goal that counts a year as "on track"
GRAY = "#8a8a8a"

d = load_all()
scope = page_header("Dashboard", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page. Everything grows from there.")
    st.stop()

contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
year = contrib_years[-1] if contrib_years else years[-1]
names = {p.key: p.name for p in d.profiles}


def card(col, label, value, sub="", color=INK, big=False, tip=""):
    size = "2.1rem" if big else "1.55rem"
    lab = f"<span title='{tip}'>{label} ⓘ</span>" if tip else label
    col.markdown(
        f"<div style='line-height:1.2;margin-bottom:.4rem'>"
        f"<div style='font-size:.72rem;letter-spacing:.04em;text-transform:uppercase;color:{GRAY}'>{lab}</div>"
        f"<div style='font-size:{size};font-weight:700;color:{color}'>{value}</div>"
        f"<div style='font-size:.78rem;color:{GRAY}'>{sub}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def stats(profiles):
    pva = compute.household_plan_vs_actual(profiles, d.income, d.targets, d.contributions, year)
    target, invested = pva["expected"].sum(), pva["actual"].sum()
    income_yr = invest_yr = 0.0
    for p in profiles:
        bs = compute.budget_series(p, d.income)
        row = bs[bs["year"] == year]
        if not row.empty:
            income_yr += row.iloc[0]["total_income"]
            invest_yr += row.iloc[0]["investment"]
    return {
        "target": target, "invested": invested, "remaining": max(target - invested, 0.0),
        "progress": compute.pct_goal_achieved(pva) if not pva.empty else 0.0,
        "rate": 100 * invest_yr / income_yr if income_yr else 0.0,
    }


# Goal progress, one card per selected person, plus the household when both are in.
st.markdown(f"##### Goal progress · {year}")
entities = [(p.name, [p]) for p in selected]
if len(selected) > 1:
    entities.append(("Household", selected))
for col, (name, profs) in zip(st.columns(len(entities)), entities):
    s = stats(profs)
    color = TEAL if s["progress"] >= ON_TRACK else MULBERRY
    card(col, name, f"{s['progress']:.0f}%", f"{inr_short(s['invested'])} of {inr_short(s['target'])}",
         color=color, big=True, tip="Share of this year's target actually invested. 100% is right on plan.")

# Headline footnote: consistency and the weakest spot.
hh = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
on_track = sum(
    1 for cy in contrib_years
    if compute.pct_goal_achieved(
        compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, cy)
    ) >= ON_TRACK
)
line = f"On track in **{on_track} of {len(contrib_years)}** years (75%+ of goal)."
if not hh.empty:
    worst = hh.loc[hh["shortfall"].idxmin()]
    if worst["shortfall"] < 0:
        line += f" Biggest gap right now: :violet[**{pretty_category(worst['category'])}**] ({inr_short(worst['shortfall'])})."
st.markdown(line)

st.divider()

# This year's numbers for the whole selection.
agg = stats(selected)
ai = compute.annual_income(d.income)
ai = ai[ai["profile"].isin(scope)]
inc_now = ai[ai["year"] == year][["salary", "bonus", "other"]].sum().sum()
inc_prev = ai[ai["year"] == year - 1][["salary", "bonus", "other"]].sum().sum()
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else "first year"
left = f"{agg['remaining'] / agg['target'] * 100:.0f}% of target left" if agg["target"] else ""

st.markdown(f"##### This year · {year}")
c = st.columns(4)
card(c[0], "Income", inr_short(inc_now), yoy)
card(c[1], "Target", inr_short(agg["target"]), "to invest this year",
     tip="Planned investment for the year (target % times budget).")
card(c[2], "Still to go", inr_short(agg["remaining"]), left, color=MULBERRY)
card(c[3], "Per month", inr_short(agg["target"] / 12), "see Monthly Plan")
invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()
st.caption(f"Investing **{agg['rate']:.0f}%** of income this year. **{inr(invested_to_date)}** invested so far, all years counted.")

# Actual invested, year by year, a line per selected person (combined when both).
st.markdown("##### Actual invested by year")
contrib = d.contributions[d.contributions["profile"].isin(scope)]
if contrib.empty:
    st.caption("Nothing recorded yet. Add contributions on the Plan vs Actual page.")
else:
    piv = contrib.groupby(["year", "profile"])["amount"].sum().unstack("profile").rename(columns=names)
    order = [p.name for p in selected if p.name in piv.columns]
    piv = piv[order]
    accents = [TEAL, MULBERRY]
    colors = [accents[i % 2] for i in range(len(order))]
    if len(order) > 1:
        piv["Combined"] = piv.sum(axis=1)
        colors.append(INK)
    st.line_chart(piv, color=colors if len(piv.columns) > 1 else colors[0])
    st.caption("What actually went in each year. No projections here, only real money.")

goals = d.goals[(d.goals["year"] == year) & (d.goals["profile"].isin(scope))]
if not goals.empty:
    st.caption(f"Emergency fund goal for {year}: {inr(goals['emergency_fund_goal'].sum())}")
