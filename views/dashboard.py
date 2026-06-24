import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from ui import (
    MULBERRY, ON_TRACK_PCT, SAND, TEAL, inr_short, load_all, metric_tile,
    page_header, pretty_category, style_fig,
)

GRAY_LINE = "#9aa0a6"

d = load_all()
profile = page_header("Dashboard", d.profiles)
today_year = dt.date.today().year

contrib = d.contributions[d.contributions["profile"] == profile.key]
bs = compute.budget_series(profile, d.income)
trend = bs[~bs["is_projected"]]
if trend.empty and contrib.empty:
    st.info(f"Nothing for {profile.name} yet. Start on the Income page.")
    st.stop()


def chart_title(text):
    st.markdown(f"<div style='font-weight:600;font-size:.95rem;color:var(--text);margin:.5rem 0 .4rem'>{text}</div>",
                unsafe_allow_html=True)


# --- hero: earning more, investing a bigger slice ----------------------------
chart_title("Earning more, investing a bigger slice")
if trend.empty:
    st.caption("Add income to see the trajectory.")
else:
    yr = trend["year"].astype(int).astype(str)
    rate_line = (100 * trend["investment"] / trend["total_income"]).round(0)
    inc_growth = ["" if pd.isna(v) else f"+{v:.0f}%" for v in trend["total_income"].pct_change() * 100]
    f = go.Figure()
    f.add_bar(x=yr, y=trend["total_income"], name="Income", marker_color=SAND,
              text=inc_growth, textposition="outside", textfont=dict(size=11, color="#6b7280"))
    f.add_bar(x=yr, y=trend["investment"], name="Investment", marker_color=TEAL)
    f.add_trace(go.Scatter(
        x=yr, y=rate_line, name="Invest rate", yaxis="y2", mode="lines+markers+text",
        text=[f"{v:.0f}%" for v in rate_line], textposition="top center",
        textfont=dict(size=11, color=MULBERRY), line=dict(color=MULBERRY, width=3), marker=dict(size=8)))
    f.update_traces(cliponaxis=False, selector=dict(type="bar"))
    f.update_layout(barmode="group", xaxis=dict(type="category"), yaxis=dict(tickprefix="₹", tickformat="~s"),
                    yaxis2=dict(overlaying="y", side="right", range=[0, max(60, rate_line.max() + 15)],
                                ticksuffix="%", showgrid=False))
    style_fig(f, height=360)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Grey labels: income growth year on year. Mulberry line: % of income invested (the rising slice).")

# --- lifetime cards ----------------------------------------------------------
nw_actual, nw_potential = compute.net_worth_to_date(profile, d.contributions, d.goals, today_year)
invested = float(contrib["amount"].sum())
nw = compute.net_worth_series(profile, d.income, d.contributions, d.targets, d.goals, today_year)

# Evaluate against every planned year up to today, not just years with a
# contribution row — a year you invested nothing is a miss, not an absence.
eval_years = [y for y in compute.available_years(d.income, d.contributions) if y <= today_year]
lifetime_planned = sum(sum(compute.expected_contributions(profile, d.income, d.targets, y).values()) for y in eval_years)
invested_in_plan = float(contrib.loc[contrib["year"].isin(eval_years), "amount"].sum())
overall = 100 * invested_in_plan / lifetime_planned if lifetime_planned else 0.0
on_track = sum(
    1 for y in eval_years
    if compute.pct_goal_achieved(compute.plan_vs_actual(profile, d.income, d.targets, d.contributions, y)) >= ON_TRACK_PCT
)
latest = trend.iloc[-1] if not trend.empty else None
rate = 100 * latest["investment"] / latest["total_income"] if latest is not None and latest["total_income"] else 0.0

st.markdown("<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-top:.6rem'>Lifetime</div>", unsafe_allow_html=True)
c = st.columns(4)
metric_tile(c[0], "Potential net worth", inr_short(nw_potential), f"≈ {inr_short(nw_potential - nw_actual)} growth",
            color=TEAL, big=True,
            help="What your contributions could be worth today, compounded at conservative per-category returns, plus your emergency fund.")
metric_tile(c[1], "Invested to date", inr_short(invested), "actual, all years", big=True,
            help="Total you have actually put in across every year (cost basis, no growth).")
metric_tile(c[2], "Overall goal", f"{overall:.0f}%", "invested of planned", big=True,
            color=TEAL if overall >= ON_TRACK_PCT else MULBERRY,
            help="Across the years you've been investing, how much of the planned amount you actually invested.")
metric_tile(c[3], "Savings rate", f"{rate:.0f}%", "of income, latest year", big=True,
            help="Share of your income the plan puts into investing. It rises as you earn more.")

# --- net worth: invested vs projected value ----------------------------------
chart_title("Net worth — invested vs projected value")
if nw.empty:
    st.caption("Record contributions on the Actuals page to project net worth.")
else:
    nyr = nw["year"].astype(int).astype(str)
    past = nw[~nw["is_projected"]]
    proj = nw[nw["year"] >= today_year]
    f = go.Figure()
    f.add_trace(go.Scatter(x=nyr, y=nw["cost_basis"], name="Invested (cost)",
                           mode="lines", line=dict(color=GRAY_LINE, width=2)))
    f.add_trace(go.Scatter(x=past["year"].astype(int).astype(str), y=past["potential"],
                           name="Net worth", mode="lines+markers", line=dict(color=TEAL, width=3)))
    if len(proj) > 1:
        f.add_trace(go.Scatter(x=proj["year"].astype(int).astype(str), y=proj["potential"],
                               name="Projected", mode="lines", line=dict(color=TEAL, width=3, dash="dash")))
    f.update_layout(xaxis=dict(type="category"), yaxis=dict(tickprefix="₹", tickformat="~s"))
    style_fig(f, height=320)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Solid: contributions compounded at conservative returns. Dashed: if you keep investing the plan. Grey: money put in (no growth).")

# --- execution: planned vs actual invested per year --------------------------
if eval_years:
    chart_title("Did you hit the plan, year by year?")
    planned = [sum(compute.expected_contributions(profile, d.income, d.targets, y).values()) for y in eval_years]
    actual = [float(contrib.loc[contrib["year"] == y, "amount"].sum()) for y in eval_years]
    xs = [str(y) for y in eval_years]
    f = go.Figure()
    f.add_bar(x=xs, y=planned, name="Planned", marker_color=MULBERRY)
    f.add_bar(x=xs, y=actual, name="Actual", marker_color=TEAL)
    f.update_layout(barmode="group", xaxis=dict(type="category"), yaxis=dict(tickprefix="₹", tickformat="~s"))
    style_fig(f, height=300)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

# --- takeaways ---------------------------------------------------------------
bullets = []
if eval_years:
    bullets.append(f"On track in <b>{on_track} of {len(eval_years)}</b> years (75%+ of plan); "
                   f"overall you've invested <b>{overall:.0f}%</b> of what you planned.")
gaps = []
for y in eval_years:
    exp = compute.expected_contributions(profile, d.income, d.targets, y)
    act = contrib[contrib["year"] == y].groupby("category")["amount"].sum().to_dict()
    for cat in set(exp) | set(act):
        gaps.append((cat, act.get(cat, 0) - exp.get(cat, 0)))
if gaps:
    agg = pd.DataFrame(gaps, columns=["category", "gap"]).groupby("category")["gap"].sum()
    behind = agg[agg < 0].sort_values().head(2)
    if not behind.empty:
        parts = [f"<b>{pretty_category(c)}</b> ({inr_short(-g)} behind)" for c, g in behind.items()]
        bullets.append("Biggest gaps over time: " + ", ".join(parts) + ".")
if not nw.empty:
    bullets.append(f"Potential net worth <b>{inr_short(nw_potential)}</b> today, heading toward "
                   f"<b>{inr_short(int(nw['potential'].iloc[-1]))}</b> by {int(nw['year'].iloc[-1])} if you keep to plan.")
if bullets:
    items = "".join(f"<li style='margin:.25rem 0'>{b}</li>" for b in bullets)
    st.markdown(
        f"<div style='margin-top:1rem'>"
        f"<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.2rem'>Takeaways</div>"
        f"<ul style='color:var(--text);margin:0;padding-left:1.1rem'>{items}</ul></div>",
        unsafe_allow_html=True,
    )
