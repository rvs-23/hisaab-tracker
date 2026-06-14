import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    INK, MULBERRY, TEAL, inr, inr_short, load_all, metric_tile, page_header,
    pretty_category, style_fig,
)

ON_TRACK = 75
SAND = "#dfe4e8"  # neutral bar for income

d = load_all()
scope = page_header("Dashboard", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page. Everything grows from there.")
    st.stop()

contrib_years = sorted(d.contributions["year"].dropna().astype(int).unique())
year = contrib_years[-1] if contrib_years else years[-1]

# --- numbers -----------------------------------------------------------------
hh = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
target, invested = hh["expected"].sum(), hh["actual"].sum()
progress = compute.pct_goal_achieved(hh) if not hh.empty else 0.0

frames = [
    compute.budget_series(p, d.income).query("is_projected == False")[["year", "total_income", "investment"]]
    for p in selected
    if not compute.budget_series(p, d.income).empty
]
trend = (
    pd.concat(frames).groupby("year", as_index=False)[["total_income", "investment"]].sum().sort_values("year")
    if frames else pd.DataFrame(columns=["year", "total_income", "investment"])
)
inc_now = float(trend.loc[trend["year"] == year, "total_income"].sum())
inc_prev = float(trend.loc[trend["year"] == year - 1, "total_income"].sum())
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else "first year"
rate_now = 100 * trend.loc[trend["year"] == year, "investment"].sum() / inc_now if inc_now else 0.0
invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()
on_track = sum(
    1 for cy in contrib_years
    if compute.pct_goal_achieved(
        compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, cy)
    ) >= ON_TRACK
)

# --- KPI strip: 8 tiles, two rows of four ------------------------------------
st.markdown(f"<div style='color:#8a8a8a;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em'>Snapshot · {year}</div>", unsafe_allow_html=True)
r1 = st.columns(4)
metric_tile(r1[0], "Goal progress", f"{progress:.0f}%", "of this year's target",
            color=TEAL if progress >= ON_TRACK else MULBERRY, big=True)
metric_tile(r1[1], "Invested", inr_short(invested), "actual, this year", big=True)
metric_tile(r1[2], "Target", inr_short(target), "planned for the year", big=True)
metric_tile(r1[3], "Still to go", inr_short(max(target - invested, 0)), "to hit the target",
            color=MULBERRY, big=True)
st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)
r2 = st.columns(4)
metric_tile(r2[0], "Income", inr_short(inc_now), yoy)
metric_tile(r2[1], "Savings rate", f"{rate_now:.0f}%", "of income invested")
metric_tile(r2[2], "Invested to date", inr_short(invested_to_date), "all years")
metric_tile(r2[3], "Years on track", f"{on_track} / {len(contrib_years)}", f"{ON_TRACK}%+ of goal")

st.write("")

# --- two charts --------------------------------------------------------------
g1, g2 = st.columns(2)

def chart_title(text):
    st.markdown(
        f"<div style='font-weight:600;font-size:.92rem;color:#3a3a3a;margin:.2rem 0 -.2rem'>{text}</div>",
        unsafe_allow_html=True,
    )


with g1:
    chart_title("Earning more, investing a bigger slice")
    if trend.empty:
        st.caption("Add income to see the trajectory.")
    else:
        yr = trend["year"].astype(int).astype(str)
        rate = (100 * trend["investment"] / trend["total_income"]).round(0)
        f = go.Figure()
        f.add_bar(x=yr, y=trend["total_income"], name="Income", marker_color=SAND)
        f.add_bar(x=yr, y=trend["investment"], name="Investment", marker_color=TEAL)
        f.add_trace(go.Scatter(
            x=yr, y=rate, name="Invest rate", yaxis="y2", mode="lines+markers",
            line=dict(color=MULBERRY, width=3), marker=dict(size=8),
        ))
        f.update_layout(
            barmode="group",
            yaxis=dict(tickprefix="₹", tickformat="~s"),
            yaxis2=dict(overlaying="y", side="right", range=[0, 100], ticksuffix="%", showgrid=False),
        )
        style_fig(f)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

with g2:
    chart_title(f"Ahead and behind, by bucket · {year}")
    if hh.empty:
        st.caption("Add contributions to see where you stand against plan.")
    else:
        gap = hh.sort_values("shortfall")
        cats = [pretty_category(c) for c in gap["category"]]
        colors = [TEAL if s >= 0 else MULBERRY for s in gap["shortfall"]]
        f = go.Figure(go.Bar(
            y=cats, x=gap["shortfall"], orientation="h", marker_color=colors,
            hovertemplate="%{y}: ₹%{x:,.0f}<extra></extra>",
        ))
        f.update_layout(xaxis=dict(tickprefix="₹", tickformat="~s"))
        style_fig(f)
        f.update_xaxes(showgrid=True, gridcolor="#eef1f3")
        f.update_yaxes(showgrid=False)
        st.plotly_chart(f, use_container_width=True, config={"displayModeBar": False})

# --- a few takeaways ---------------------------------------------------------
bullets = [f"On track in <b>{on_track} of {len(contrib_years)}</b> years (75%+ of goal)."]
if not hh.empty:
    worst = hh.loc[hh["shortfall"].idxmin()]
    if worst["shortfall"] < 0:
        bullets.append(f"Biggest gap right now: <b>{pretty_category(worst['category'])}</b>, {inr_short(-worst['shortfall'])} behind.")
    else:
        bullets.append("Every bucket is at or above plan this year.")
if len(trend) > 1:
    first = trend.iloc[0]
    f_rate = 100 * first["investment"] / first["total_income"] if first["total_income"] else 0
    bullets.append(f"Savings rate up from <b>{f_rate:.0f}%</b> in {int(first['year'])} to <b>{rate_now:.0f}%</b> now.")

items = "".join(f"<li style='margin:.2rem 0'>{b}</li>" for b in bullets)
st.markdown(
    f"<div style='margin-top:1.5rem'>"
    f"<div style='color:#8a8a8a;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem'>Takeaways</div>"
    f"<ul style='color:#444;margin:0;padding-left:1.1rem'>{items}</ul></div>",
    unsafe_allow_html=True,
)
