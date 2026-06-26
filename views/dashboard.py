import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from ui import (
    ON_TRACK_PCT, SAND, accent_primary, accent_secondary, info_icon, inr_short,
    load_all, metric_tile, page_header, style_fig,
)

GRAY_LINE = "#9aa0a6"

d = load_all()
profile = page_header("Dashboard", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
today_year = dt.date.today().year

contrib = d.contributions[d.contributions["profile"] == profile.key]
bs = compute.budget_series(profile, d.income)
trend = bs[~bs["is_projected"]]
if trend.empty and contrib.empty:
    st.info("Nothing here yet. Start on the Income page.")
    st.stop()


def chart_title(text, help=""):
    info = info_icon(help) if help else ""
    st.markdown(f"<div style='font-weight:600;font-size:.95rem;color:var(--text);margin:.5rem 0 .4rem'>{text}{info}</div>",
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
    f.add_bar(x=yr, y=trend["investment"], name="Investment", marker_color=PRIMARY)
    f.add_trace(go.Scatter(
        x=yr, y=rate_line, name="Invest rate", yaxis="y2", mode="lines+markers+text",
        text=[f"{v:.0f}%" for v in rate_line], textposition="top center",
        textfont=dict(size=11, color=SECONDARY), line=dict(color=SECONDARY, width=3), marker=dict(size=8)))
    f.update_traces(cliponaxis=False, selector=dict(type="bar"))
    f.update_layout(barmode="group", xaxis=dict(type="category"), yaxis=dict(tickprefix="₹", tickformat="~s"),
                    yaxis2=dict(overlaying="y", side="right", range=[0, max(60, rate_line.max() + 15)],
                                ticksuffix="%", showgrid=False))
    style_fig(f, height=360)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Grey labels: income growth year on year. Coloured line: % of income invested (the rising slice).")

# --- lifetime cards ----------------------------------------------------------
nw_actual, nw_potential = compute.net_worth_to_date(profile, d.income, d.contributions, today_year)
invested = float(contrib["amount"].sum())
nw = compute.net_worth_series(profile, d.income, d.contributions, d.targets, today_year)
catch_up = compute.catch_up_amount(profile, d.income, d.targets, d.contributions, today_year)

# Evaluate against every planned year up to today, not just years with a
# contribution row — a year you invested nothing is a miss, not an absence.
# Scoped to the active person so the other profile's years don't leak in.
eval_years = [y for y in compute.available_years(d.income, d.contributions, profile.key) if y <= today_year]
lifetime_planned = sum(sum(compute.expected_contributions(profile, d.income, d.targets, y).values()) for y in eval_years)
invested_in_plan = float(contrib.loc[contrib["year"].isin(eval_years), "amount"].sum())
overall = 100 * invested_in_plan / lifetime_planned if lifetime_planned else 0.0
latest = trend.iloc[-1] if not trend.empty else None
rate = 100 * latest["investment"] / latest["total_income"] if latest is not None and latest["total_income"] else 0.0

st.markdown("<div style='color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;margin-top:.6rem'>Lifetime</div>", unsafe_allow_html=True)
c = st.columns(4)
metric_tile(c[0], "Potential net worth", inr_short(nw_potential), f"≈ {inr_short(nw_potential - nw_actual)} growth",
            color=PRIMARY, big=True,
            help="What your contributions could be worth today, compounded at conservative per-category returns, plus your emergency fund (6 months of needs).")
metric_tile(c[1], "Invested to date", inr_short(invested), "actual, all years", big=True,
            help="Total you have actually put in across every year (cost basis, no growth).")
metric_tile(c[2], "Overall goal", f"{overall:.0f}%", "invested of planned", big=True,
            color=PRIMARY if overall >= ON_TRACK_PCT else SECONDARY,
            help="Across the years you've been investing, how much of the planned amount you actually invested.")
metric_tile(c[3], "Savings rate", f"{rate:.0f}%", "of income, latest year", big=True,
            help="Share of your income the plan puts into investing. It rises as you earn more.")

# --- catch-up: one number, one action ----------------------------------------
if catch_up > 0:
    st.markdown(
        f"<div style='border:1px solid {SECONDARY}33;background:{SECONDARY}0d;border-radius:12px;"
        f"padding:14px 18px;margin-top:.7rem;display:flex;align-items:baseline;gap:.8rem;flex-wrap:wrap'>"
        f"<span style='font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em'>"
        f"Catch up in {today_year}</span>"
        f"<span style='font-size:1.7rem;font-weight:700;color:{SECONDARY}'>{inr_short(catch_up)}</span>"
        f"<span style='font-size:.85rem;color:var(--muted)'>invest this much extra today and you're level with "
        f"every year you fell short (grown at expected returns). Overshooting is fine.</span></div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"<div style='border:1px solid {PRIMARY}33;background:{PRIMARY}0d;border-radius:12px;"
        f"padding:12px 18px;margin-top:.7rem;color:{PRIMARY};font-weight:600;font-size:.92rem'>"
        f"You're level with the plan — no catch-up needed in {today_year}. Anything extra overshoots the goal.</div>",
        unsafe_allow_html=True,
    )

# --- net worth: invested vs projected value ----------------------------------
chart_title("Net worth — invested vs projected value",
            help="An estimate, not your real portfolio value. It compounds what you've "
                 "contributed at conservative per-category expected returns (plus the emergency "
                 "fund) — it does not read live prices or what your holdings are actually worth today.")
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
                           name="Net worth", mode="lines+markers", line=dict(color=PRIMARY, width=3)))
    if len(proj) > 1:
        f.add_trace(go.Scatter(x=proj["year"].astype(int).astype(str), y=proj["potential"],
                               name="Projected", mode="lines", line=dict(color=PRIMARY, width=3, dash="dash")))
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
    f.add_bar(x=xs, y=planned, name="Planned", marker_color=SECONDARY)
    f.add_bar(x=xs, y=actual, name="Actual", marker_color=PRIMARY)
    f.update_layout(barmode="group", xaxis=dict(type="category"), yaxis=dict(tickprefix="₹", tickformat="~s"))
    style_fig(f, height=300)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
