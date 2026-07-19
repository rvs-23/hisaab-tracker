import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from ui import (
    FS_BODY, FS_HERO, FS_LABEL, INK, accent_primary, accent_secondary, chart_title,
    inr_axis, inr_short, load_all, metric_tile, page_header, pretty_category,
    section, style_fig,
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

# The years actually entered (not projected), for tile helps that must name the
# real span covered instead of the vague "all years".
entered_years = trend["year"].astype(int).tolist()
if not entered_years and not contrib.empty:
    entered_years = sorted(contrib["year"].dropna().astype(int).unique().tolist())
year_range = (
    str(entered_years[0]) if len(entered_years) == 1
    else f"{entered_years[0]}–{entered_years[-1]}" if entered_years
    else "no years yet"
)

catch_up = compute.catch_up_amount(profile, d.income, d.targets, d.contributions, today_year)
earned = float(trend["total_income"].sum())
invested = float(contrib["amount"].sum())
nw_actual, nw_potential = compute.net_worth_to_date(profile, d.income, d.contributions, today_year)

section("Lifetime")
c = st.columns(4)
metric_tile(c[0], "Earned till date", inr_short(earned), year_range, big=True,
            help=f"Total income across the years you've entered ({year_range}).")
metric_tile(c[1], "Invested till date", inr_short(invested), year_range, big=True,
            help=f"Total you've actually put in across {year_range} (cost basis, no growth).")
metric_tile(c[2], "Estimated value today", inr_short(nw_potential), f"as of {today_year}",
            color=PRIMARY, big=True,
            help=f"What your contributions across {year_range} could be worth today, "
                 "compounded at conservative per-category returns, plus your emergency "
                 "fund (6 months of needs).")
metric_tile(c[3], "Catch-up from plan", inr_short(catch_up),
            "you're on track" if catch_up == 0 else f"in {today_year}",
            color=SECONDARY if catch_up > 0 else PRIMARY, big=True,
            help=f"Lump sum, invested today, to be level with the plan across {year_range} "
                 f"(shortfalls grown at expected returns; {today_year} counts only its "
                 "elapsed share). Overshooting is fine.")

# The journey: goal vs actual investment per year, income riding along as a line
# on the same rupee axis (one axis only — dual axes hinder honest comparison).
chart_title("The journey, year on year",
            help=f"Goal is that year's planned investment ({today_year} counts only its "
                 "elapsed share so far). Income is total earnings that year.")
if trend.empty:
    st.caption("Add income to see the trajectory.")
else:
    yr = trend["year"].astype(int)
    xs = yr.astype(str)
    fraction = compute.elapsed_year_fraction()
    goal = []
    for y in yr:
        g = sum(compute.expected_contributions(profile, d.income, d.targets, int(y)).values())
        if int(y) == today_year:
            g *= fraction
        goal.append(g)
    actual_invested = [float(contrib.loc[contrib["year"] == y, "amount"].sum()) for y in yr]
    income_line = trend["total_income"].tolist()
    growth = ["" if pd.isna(v) else f"+{v:.0f}%" for v in trend["total_income"].pct_change() * 100]

    f = go.Figure()
    f.add_bar(x=xs, y=goal, name="Goal", marker_color=SECONDARY)
    f.add_bar(x=xs, y=actual_invested, name="Invested", marker_color=PRIMARY)
    f.add_trace(go.Scatter(
        x=xs, y=income_line, name="Income", mode="lines+markers+text",
        line=dict(color=INK, width=2), marker=dict(size=6, color=INK),
        text=growth, textposition="top center", textfont=dict(size=11, color=INK),
    ))
    f.update_layout(barmode="group", xaxis=dict(type="category"), showlegend=True)
    inr_axis(f, max(income_line + goal + actual_invested))
    style_fig(f, height=360)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Bars: planned goal vs what you actually invested. Line: total income, "
               "labelled with its year-on-year growth.")

# Net worth: invested vs projected value.
nw = compute.net_worth_series(profile, d.income, d.contributions, d.targets, today_year)
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
    f.update_layout(xaxis=dict(type="category"))
    inr_axis(f, nw["potential"].max())
    style_fig(f, height=320)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Solid: contributions compounded at conservative returns. Dashed: if you keep investing the plan. Grey: money put in (no growth).")

# Allocation today: cumulative contributions to date, by category.
chart_title("Allocation today",
            help="How everything you've contributed so far splits across instruments.")
by_category = contrib.groupby("category")["amount"].sum()
by_category = by_category[by_category > 0].sort_values()
if by_category.empty:
    st.caption("Record a contribution on Actuals to see how it's split.")
else:
    total = by_category.sum()
    labels = [pretty_category(cat) for cat in by_category.index]
    share = [f"{100 * v / total:.0f}%" for v in by_category]
    f = go.Figure()
    f.add_bar(y=labels, x=by_category.values, orientation="h", marker_color=PRIMARY,
              text=share, textposition="outside")
    f.update_layout(showlegend=False)
    inr_axis(f, by_category.max(), axis="x")
    style_fig(f, height=max(220, 40 * len(labels)))
    f.update_yaxes(showgrid=False)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

# Catch-up callout last: the one number to act on, once you've seen the journey.
if catch_up > 0:
    st.markdown(
        f"<div style='border:1px solid {SECONDARY}33;background:{SECONDARY}0d;border-radius:12px;"
        f"padding:14px 18px;display:flex;align-items:baseline;gap:.8rem;flex-wrap:wrap'>"
        f"<span style='font-size:{FS_LABEL};color:var(--muted);text-transform:uppercase;letter-spacing:.05em'>"
        f"Catch up in {today_year}</span>"
        f"<span style='font-size:{FS_HERO};font-weight:700;color:{SECONDARY}'>{inr_short(catch_up)}</span>"
        f"<span style='font-size:{FS_BODY};color:var(--muted)'>invest this much extra today and you're level with "
        f"every year you fell short (grown at expected returns). Overshooting is fine.</span></div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"<div style='border:1px solid {PRIMARY}33;background:{PRIMARY}0d;border-radius:12px;"
        f"padding:12px 18px;color:{PRIMARY};font-weight:600;font-size:{FS_BODY}'>"
        f"You're level with the plan — no catch-up needed in {today_year}. Anything extra overshoots the goal.</div>",
        unsafe_allow_html=True,
    )
