import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from ui import (
    MULBERRY, ON_TRACK_PCT as ON_TRACK, SAND, TEAL, inr_short, load_all,
    metric_tile, page_header, pretty_category, style_fig,
)

d = load_all()
profile = page_header("Dashboard", d.profiles)
selected = [profile]
scope = [profile.key]

years = compute.available_years(d.income, d.contributions)
if not years:
    st.info("Start on the Income page. Everything grows from there.")
    st.stop()

# Derive each selected person's budget once, then reuse everywhere (DRY).
budgets = {p.key: compute.budget_series(p, d.income) for p in selected}
trend = pd.concat(
    [b[~b["is_projected"]][["year", "total_income", "investment"]] for b in budgets.values() if not b.empty]
).groupby("year", as_index=False)[["total_income", "investment"]].sum().sort_values("year") \
    if any(not b.empty for b in budgets.values()) else pd.DataFrame(columns=["year", "total_income", "investment"])


def tv(col, yr):
    s = trend.loc[trend["year"] == yr, col]
    return float(s.sum()) if not s.empty else 0.0


# --- hero chart first: earning more, investing a bigger slice ----------------
st.markdown("<div style='font-weight:600;font-size:.95rem;color:var(--text);margin:.2rem 0 .4rem'>Earning more, investing a bigger slice</div>", unsafe_allow_html=True)
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
    f.update_layout(barmode="group", yaxis=dict(tickprefix="₹", tickformat="~s"),
                    yaxis2=dict(overlaying="y", side="right", range=[0, max(60, rate_line.max() + 15)],
                                ticksuffix="%", showgrid=False))
    style_fig(f, height=380)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Grey labels: income growth year on year. Mulberry line: % of income invested (the rising slice).")

# --- year-specific snapshot --------------------------------------------------
this_year = dt.date.today().year
default_year = this_year if this_year in years else years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", years, index=years.index(default_year))

hh = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
target, invested = hh["expected"].sum(), hh["actual"].sum()
progress = compute.pct_goal_achieved(hh) if not hh.empty else 0.0
pending = max(target - invested, 0.0)
inc_now, inc_prev = tv("total_income", year), tv("total_income", year - 1)
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else "first year"
rate = 100 * tv("investment", year) / inc_now if inc_now else 0.0

st.markdown(f"<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em'>Snapshot · {year}</div>", unsafe_allow_html=True)
c = st.columns(3)
metric_tile(c[0], "Goal progress", f"{progress:.0f}%", f"{inr_short(invested)} of {inr_short(target)}",
            color=TEAL if progress >= ON_TRACK else MULBERRY, big=True,
            help="How much of this year's investment plan you have actually put in so far. 100% means you are exactly on plan.")
metric_tile(c[1], "Income", inr_short(inc_now), yoy, big=True,
            help="Your total income this year, and the change versus last year.")
metric_tile(c[2], "Savings rate", f"{rate:.0f}%", "of income invested", big=True,
            help="The share of your income your plan puts into investing. It rises as you earn more.")

invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()
st.markdown(
    f"<div title='Total you have actually invested across every year on record.' "
    f"style='border:1px solid var(--strip-border);background:var(--strip-bg);border-radius:12px;padding:11px 18px;"
    f"margin-top:.6rem;display:flex;justify-content:space-between;align-items:center'>"
    f"<div style='color:var(--strip-text);font-size:.72rem;text-transform:uppercase;letter-spacing:.05em'>All time · invested to date &#9432;</div>"
    f"<div style='font-size:1.4rem;font-weight:700;color:var(--strip-text)'>{inr_short(invested_to_date)}</div></div>",
    unsafe_allow_html=True,
)

# --- takeaways (dynamic) -----------------------------------------------------
bullets = []
if target > 0:
    if pending > 0:
        bullets.append(f"<b>{inr_short(pending)}</b> still to invest in {year}. "
                       f"That's about <b>{inr_short(pending / 12)}/month</b> to reach your goal.")
    else:
        bullets.append(f"Goal met for {year}: <b>{inr_short(invested)}</b> invested of {inr_short(target)}.")
gaps = hh[hh["shortfall"] < 0].sort_values("shortfall").head(2) if not hh.empty else hh
if not gaps.empty:
    parts = [f"<b>{pretty_category(r['category'])}</b> ({inr_short(-r['shortfall'])} behind)" for _, r in gaps.iterrows()]
    bullets.append("Biggest gaps: " + ", ".join(parts) + ".")
if not bullets:
    bullets.append(f"Add income and a target to see what to invest for {year}.")

items = "".join(f"<li style='margin:.25rem 0'>{b}</li>" for b in bullets)
st.markdown(
    f"<div style='margin-top:1.2rem'>"
    f"<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.2rem'>Takeaways · {year}</div>"
    f"<ul style='color:var(--text);margin:0;padding-left:1.1rem'>{items}</ul></div>",
    unsafe_allow_html=True,
)
