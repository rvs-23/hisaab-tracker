import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    MULBERRY, ON_TRACK_PCT as ON_TRACK, SAND, TEAL, grid_color, inr_short,
    load_all, metric_tile, page_header, pretty_category, style_fig,
)

d = load_all()
scope = page_header("Dashboard", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page. Everything grows from there.")
    st.stop()

this_year = dt.date.today().year
default_year = this_year if this_year in years else years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", years, index=years.index(default_year))

# multi-year trajectory (actual, non-projected years) for the trend chart
frames = [
    compute.budget_series(p, d.income).query("is_projected == False")[["year", "total_income", "investment"]]
    for p in selected
    if not compute.budget_series(p, d.income).empty
]
trend = (
    pd.concat(frames).groupby("year", as_index=False)[["total_income", "investment"]].sum().sort_values("year")
    if frames else pd.DataFrame(columns=["year", "total_income", "investment"])
)


def tv(col, yr):
    s = trend.loc[trend["year"] == yr, col]
    return float(s.sum()) if not s.empty else 0.0


# --- year-specific snapshot --------------------------------------------------
hh = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
target, invested = hh["expected"].sum(), hh["actual"].sum()
progress = compute.pct_goal_achieved(hh) if not hh.empty else 0.0
remaining = max(target - invested, 0.0)
inc_now, inc_prev = tv("total_income", year), tv("total_income", year - 1)
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else "first year"
rate = 100 * tv("investment", year) / inc_now if inc_now else 0.0

st.markdown(f"<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em'>Snapshot · {year}</div>", unsafe_allow_html=True)
c = st.columns(3)
metric_tile(c[0], "Goal progress", f"{progress:.0f}%", f"{inr_short(invested)} of {inr_short(target)}",
            color=TEAL if progress >= ON_TRACK else MULBERRY, big=True)
metric_tile(c[1], "Income", inr_short(inc_now), yoy, big=True)
metric_tile(c[2], "Savings rate", f"{rate:.0f}%", "of income invested", big=True)

# --- all-time, set apart -----------------------------------------------------
invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()
st.markdown(
    f"<div style='border:1px solid var(--strip-border);background:var(--strip-bg);border-radius:12px;padding:11px 18px;"
    f"margin-top:.6rem;display:flex;justify-content:space-between;align-items:center'>"
    f"<div style='color:var(--strip-text);font-size:.72rem;text-transform:uppercase;letter-spacing:.05em'>All time · invested to date</div>"
    f"<div style='font-size:1.4rem;font-weight:700;color:var(--strip-text)'>{inr_short(invested_to_date)}</div></div>",
    unsafe_allow_html=True,
)
st.write("")


def chart_title(text):
    st.markdown(f"<div style='font-weight:600;font-size:.92rem;color:var(--text);margin:.2rem 0 .6rem'>{text}</div>",
                unsafe_allow_html=True)


g1, g2 = st.columns(2)

with g1:
    chart_title("Earning more, investing a bigger slice")
    if trend.empty:
        st.caption("Add income to see the trajectory.")
    else:
        yr = trend["year"].astype(int).astype(str)
        rate_line = (100 * trend["investment"] / trend["total_income"]).round(0)
        inv_text = ["" if pd.isna(v) else f"{v:+.0f}%" for v in trend["investment"].pct_change() * 100]
        f = go.Figure()
        f.add_bar(x=yr, y=trend["total_income"], name="Income", marker_color=SAND)
        f.add_bar(x=yr, y=trend["investment"], name="Investment", marker_color=TEAL,
                  text=inv_text, textposition="outside", textfont=dict(size=10, color=TEAL))
        f.add_trace(go.Scatter(x=yr, y=rate_line, name="Invest rate", yaxis="y2",
                               mode="lines+markers", line=dict(color=MULBERRY, width=3), marker=dict(size=8)))
        f.update_traces(cliponaxis=False, selector=dict(type="bar"))
        f.update_layout(barmode="group", yaxis=dict(tickprefix="₹", tickformat="~s"),
                        yaxis2=dict(overlaying="y", side="right", range=[0, 100], ticksuffix="%", showgrid=False))
        style_fig(f)
        st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

with g2:
    chart_title(f"Plan vs actual, by bucket · {year}")
    if hh.empty:
        st.caption("No plan for this year yet.")
    else:
        gp = hh.sort_values("expected")
        cats = [pretty_category(x) for x in gp["category"]]
        f = go.Figure()
        f.add_bar(y=cats, x=gp["expected"], name="Planned", orientation="h", marker_color=MULBERRY)
        f.add_bar(y=cats, x=gp["actual"], name="Actual", orientation="h", marker_color=TEAL)
        f.update_layout(barmode="group", xaxis=dict(tickprefix="₹", tickformat="~s"))
        style_fig(f)
        f.update_xaxes(showgrid=True, gridcolor=grid_color())
        f.update_yaxes(showgrid=False)
        st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

# --- takeaways (year-specific, never empty) ----------------------------------
bullets = []
if invested > 0:
    bullets.append(f"<b>{progress:.0f}%</b> to {year}'s goal, {inr_short(remaining)} still to invest.")
    if not hh.empty:
        worst = hh.loc[hh["shortfall"].idxmin()]
        if worst["shortfall"] < 0:
            bullets.append(f"Furthest behind: <b>{pretty_category(worst['category'])}</b>, {inr_short(-worst['shortfall'])} short.")
        best = hh.loc[hh["shortfall"].idxmax()]
        if best["shortfall"] > 0:
            bullets.append(f"Ahead on <b>{pretty_category(best['category'])}</b> by {inr_short(best['shortfall'])}.")
elif target > 0:
    bullets.append(f"Plan for {year}: invest <b>{inr_short(target)}</b> ({inr_short(target / 12)}/mo). Nothing recorded yet.")
    bullets.append(f"That's <b>{rate:.0f}%</b> of your {inr_short(inc_now)} income this year.")
else:
    bullets.append(f"No plan for {year} yet. Add income to set the budget.")

items = "".join(f"<li style='margin:.2rem 0'>{b}</li>" for b in bullets)
st.markdown(
    f"<div style='margin-top:1.2rem'>"
    f"<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.2rem'>Takeaways · {year}</div>"
    f"<ul style='color:var(--text);margin:0;padding-left:1.1rem'>{items}</ul></div>",
    unsafe_allow_html=True,
)
