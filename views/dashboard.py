import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    INK, MULBERRY, TEAL, inr_short, load_all, metric_tile, page_header,
    pretty_category, style_fig,
)

ON_TRACK = 75
SAND = "#dfe4e8"

d = load_all()
scope = page_header("Dashboard", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page. Everything grows from there.")
    st.stop()

# Year selector, defaulting to the current calendar year.
this_year = dt.date.today().year
default_year = this_year if this_year in years else years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", years, index=years.index(default_year))

# --- per-year trajectory (actual, non-projected years) -----------------------
frames = [
    compute.budget_series(p, d.income).query("is_projected == False")[["year", "total_income", "investment"]]
    for p in selected
    if not compute.budget_series(p, d.income).empty
]
trend = (
    pd.concat(frames).groupby("year", as_index=False)[["total_income", "investment"]].sum().sort_values("year")
    if frames else pd.DataFrame(columns=["year", "total_income", "investment"])
)


def trend_val(col, yr):
    s = trend.loc[trend["year"] == yr, col]
    return float(s.sum()) if not s.empty else 0.0


# --- the four cards ----------------------------------------------------------
hh = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
target, invested = hh["expected"].sum(), hh["actual"].sum()
progress = compute.pct_goal_achieved(hh) if not hh.empty else 0.0
inc_now, inc_prev = trend_val("total_income", year), trend_val("total_income", year - 1)
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else "first year"
rate = 100 * trend_val("investment", year) / inc_now if inc_now else 0.0
invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()

st.markdown(f"<div style='color:#8a8a8a;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em'>Snapshot · {year}</div>", unsafe_allow_html=True)
c = st.columns(4)
metric_tile(c[0], "Goal progress", f"{progress:.0f}%", f"{inr_short(invested)} of {inr_short(target)}",
            color=TEAL if progress >= ON_TRACK else MULBERRY, big=True)
metric_tile(c[1], "Income", inr_short(inc_now), yoy, big=True)
metric_tile(c[2], "Savings rate", f"{rate:.0f}%", "of income invested", big=True)
metric_tile(c[3], "Invested to date", inr_short(invested_to_date), "all years, actual", big=True)

st.write("")


def chart_title(text):
    st.markdown(
        f"<div style='font-weight:600;font-size:.92rem;color:#3a3a3a;margin:.2rem 0 .6rem'>{text}</div>",
        unsafe_allow_html=True,
    )


g1, g2 = st.columns(2)

with g1:
    chart_title("Earning more, investing a bigger slice")
    if trend.empty:
        st.caption("Add income to see the trajectory.")
    else:
        yr = trend["year"].astype(int).astype(str)
        rate_line = (100 * trend["investment"] / trend["total_income"]).round(0)
        inc_text = ["" if pd.isna(v) else f"{v:+.0f}%" for v in trend["total_income"].pct_change() * 100]
        inv_text = ["" if pd.isna(v) else f"{v:+.0f}%" for v in trend["investment"].pct_change() * 100]
        f = go.Figure()
        f.add_bar(x=yr, y=trend["total_income"], name="Income", marker_color=SAND,
                  text=inc_text, textposition="outside", textfont=dict(size=10, color="#9aa0a6"))
        f.add_bar(x=yr, y=trend["investment"], name="Investment", marker_color=TEAL,
                  text=inv_text, textposition="outside", textfont=dict(size=10, color=TEAL))
        f.add_trace(go.Scatter(x=yr, y=rate_line, name="Invest rate", yaxis="y2",
                               mode="lines+markers", line=dict(color=MULBERRY, width=3), marker=dict(size=8)))
        f.update_traces(cliponaxis=False, selector=dict(type="bar"))
        f.update_layout(
            barmode="group",
            yaxis=dict(tickprefix="₹", tickformat="~s"),
            yaxis2=dict(overlaying="y", side="right", range=[0, 100], ticksuffix="%", showgrid=False),
        )
        style_fig(f)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

# Cumulative plan vs actual across every year with contributions.
contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
cum_parts = [
    compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, cy) for cy in contrib_years
]
cum = (
    pd.concat(cum_parts).groupby("category", as_index=False)[["expected", "actual", "shortfall"]].sum()
    if cum_parts else pd.DataFrame(columns=["category", "expected", "actual", "shortfall"])
)

with g2:
    chart_title("Ahead and behind, by bucket (all years)")
    if cum.empty:
        st.caption("Add contributions to see where you stand against plan.")
    else:
        gap = cum.sort_values("shortfall")
        colors = [TEAL if s >= 0 else MULBERRY for s in gap["shortfall"]]
        f = go.Figure(go.Bar(y=[pretty_category(x) for x in gap["category"]], x=gap["shortfall"],
                             orientation="h", marker_color=colors,
                             hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>"))
        f.update_layout(xaxis=dict(tickprefix="₹", tickformat="~s"))
        style_fig(f)
        f.update_xaxes(showgrid=True, gridcolor="#eef1f3")
        f.update_yaxes(showgrid=False)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

# --- takeaway ----------------------------------------------------------------
if not cum.empty:
    worst = cum.loc[cum["shortfall"].idxmin()]
    msg = (f"Biggest gap so far: <b>{pretty_category(worst['category'])}</b>, {inr_short(-worst['shortfall'])} behind across all years."
           if worst["shortfall"] < 0 else "Every bucket is at or above plan so far.")
    st.markdown(
        f"<div style='margin-top:1.2rem'>"
        f"<div style='color:#8a8a8a;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem'>Takeaway</div>"
        f"<div style='color:#444'>• {msg}</div></div>",
        unsafe_allow_html=True,
    )
