import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from ui import (
    CHART_TEXT, FS_BODY, FS_HERO, FS_LABEL, SAND, accent_primary,
    accent_secondary, chart_title, inr_axis, inr_short, is_household, load_all, metric_tile,
    page_header, pretty_category, section, style_fig,
)

d = load_all()
profile = page_header("Dashboard", d.profiles, d.root, allow_household=True)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
today_year = dt.date.today().year
# The household view sums every figure over both people; a person's view is
# the same code over a list of one.
household = is_household(profile)
people = d.profiles if household else [profile]
keys = [p.key for p in people]

contrib = d.contributions[d.contributions["profile"].isin(keys)]
bs = pd.concat([compute.budget_series(p, d.income) for p in people], ignore_index=True)
trend = (bs[~bs["is_projected"].astype(bool)]
         .groupby("year", as_index=False)[["total_income", "investment"]].sum()
         if not bs.empty else bs)
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

catch_up = sum(compute.catch_up_amount(p, d.income, d.targets, d.contributions, today_year)
               for p in people)
earned = float(trend["total_income"].sum())
opening = sum(compute.opening_corpus(d.adjustments, p.key) for p in people)
invested = float(contrib["amount"].sum()) + opening


def year_goal_for(year: int) -> float:
    """The planned investment for a year, summed over the people shown."""
    return sum(sum(compute.expected_contributions(p, d.income, d.targets, year).values())
               for p in people)


year_goal = year_goal_for(today_year)
invested_ty = float(contrib.loc[contrib["year"] == today_year, "amount"].sum())
to_go = max(0.0, year_goal - invested_ty)

# The one number to act on, first: everything still needed to be on plan by
# December (this year's remainder plus past years' shortfall), and what that is
# per remaining month.
needed = to_go + catch_up
if needed > 0:
    n = compute.months_left()
    parts = [f"{inr_short(to_go)} left of {today_year}'s goal"] if to_go > 0 else []
    if catch_up > 0:
        parts.append(f"{inr_short(catch_up)} past years' shortfall")
    st.markdown(
        f"<div style='border:1px solid {SECONDARY}33;background:{SECONDARY}0d;border-radius:12px;"
        f"padding:14px 18px;display:flex;align-items:baseline;gap:.8rem;flex-wrap:wrap'>"
        f"<span style='font-size:{FS_LABEL};color:var(--muted);text-transform:uppercase;letter-spacing:.05em'>"
        f"To be on plan by Dec {today_year}</span>"
        f"<span style='font-size:{FS_HERO};font-weight:700;color:{SECONDARY}'>{inr_short(needed)}</span>"
        f"<span style='font-size:{FS_BODY};color:var(--muted)'>{' + '.join(parts)}. That's about "
        f"<b>{inr_short(needed / n)} a month</b> for {compute.month_span()}.</span></div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f"<div style='border:1px solid {PRIMARY}33;background:{PRIMARY}0d;border-radius:12px;"
        f"padding:12px 18px;color:{PRIMARY};font-weight:600;font-size:{FS_BODY}'>"
        f"You're on plan for {today_year} and every past year. Anything extra overshoots the goal.</div>",
        unsafe_allow_html=True,
    )

section("Lifetime")
c = st.columns(3)
metric_tile(c[0], "Earned till date", inr_short(earned), year_range, big=True,
            help=f"Total income across the years you've entered ({year_range}).")
invested_help = f"Total you've actually put in across {year_range} (cost basis, no growth)."
if opening > 0:
    invested_help += f" Includes {inr_short(opening)} invested before tracking."
metric_tile(c[1], "Invested till date", inr_short(invested), year_range, big=True,
            help=invested_help)
# The plan tile headlines the TOTAL to invest to be fully on track: this
# year's goal plus the catch-up from past years. The sub-lines split it.
plan_sub = (
    ("no past shortfall" if catch_up == 0 else f"past years' shortfall: {inr_short(catch_up)}")
    + "<br>"
    + (f"{today_year} left: {inr_short(to_go)}" if to_go > 0 else f"{today_year} goal met")
)
metric_tile(c[2], f"{today_year} total goal", inr_short(year_goal + catch_up), plan_sub,
            color=SECONDARY, big=True,
            help=f"{today_year}'s goal ({inr_short(year_goal)}) plus the shortfall from "
                 f"past years ({inr_short(catch_up)}). "
                 f"'{today_year} left' is the year's goal minus the {inr_short(invested_ty)} "
                 "you've already put in. Overshooting is fine.")

# The journey: income and the goal as bars, actual investment riding along as
# a line, all on one shared rupee axis (one axis only — dual axes hinder
# honest comparison).
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
        g = year_goal_for(int(y))
        if int(y) == today_year:
            g *= fraction
        goal.append(g)
    actual_invested = [float(contrib.loc[contrib["year"] == y, "amount"].sum()) for y in yr]
    income_bars = trend["total_income"].tolist()
    growth = ["" if pd.isna(v) else f"{v:+.0f}%" for v in trend["total_income"].pct_change() * 100]

    # The target % of income (the plan's investment share) rides each goal bar
    # as a small outside label — outside, so tiny bars can't clip it.
    target_pct = [f"{100 * inv / tot:.0f}%" if tot else ""
                  for inv, tot in zip(trend["investment"], trend["total_income"])]
    f = go.Figure()
    f.add_bar(
        x=xs, y=income_bars, name="Income", marker_color=SAND,
        text=growth, textposition="outside", textfont=dict(size=11, color=CHART_TEXT),
    )
    f.add_bar(x=xs, y=goal, name="Goal", marker_color=SECONDARY,
              text=target_pct, textposition="outside",
              textfont=dict(size=10, color=SECONDARY))
    f.add_trace(go.Scatter(
        x=xs, y=actual_invested, name="Invested", mode="lines+markers",
        line=dict(color=PRIMARY, width=3), marker=dict(size=6, color=PRIMARY),
    ))
    f.update_traces(cliponaxis=False, selector=dict(type="bar"))
    f.update_layout(barmode="group", xaxis=dict(type="category"), showlegend=True)
    inr_axis(f, max(income_bars + goal + actual_invested), step=10_00_000)
    style_fig(f, height=360)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
    st.caption("Bars: income and the planned goal (the small % is the share of income the plan targets to invest). Line: what you actually invested.")


# Your mix against the plan, all years so far: each instrument's share of what
# you actually put in beside its share of what the plan asked for. Actual wears
# the primary accent, plan the secondary, as everywhere.
chart_title("Your mix vs the plan, all years so far",
            help="Each instrument's share of everything you've invested, beside its share "
                 "of everything the plan asked for over the same years.")
plan_total: dict[str, float] = {}
for y in sorted(int(v) for v in contrib["year"].dropna().unique()):
    for p in people:
        for cat, amt in compute.expected_contributions(p, d.income, d.targets, y).items():
            plan_total[cat] = plan_total.get(cat, 0.0) + amt
actual_total = contrib.groupby("category")["amount"].sum().to_dict()
cats = [c for c in d.config.categories if actual_total.get(c, 0) > 0 or plan_total.get(c, 0) > 0]
if not cats:
    st.caption("Record an investment on Investments to see how it's split.")
else:
    a_sum, p_sum = sum(actual_total.values()) or 1, sum(plan_total.values()) or 1
    a_pct = [100 * actual_total.get(c, 0) / a_sum for c in cats]
    p_pct = [100 * plan_total.get(c, 0) / p_sum for c in cats]
    labels = [pretty_category(c) for c in cats][::-1]
    f = go.Figure()
    f.add_bar(y=labels, x=p_pct[::-1], name="Plan", orientation="h", marker_color=SECONDARY,
              text=[f"{v:.0f}%" for v in p_pct[::-1]], textposition="outside")
    f.add_bar(y=labels, x=a_pct[::-1], name="Actual", orientation="h", marker_color=PRIMARY,
              text=[f"{v:.0f}%" for v in a_pct[::-1]], textposition="outside")
    f.update_traces(cliponaxis=False)
    f.update_layout(barmode="group", xaxis=dict(ticksuffix="%", range=[0, 1.15 * max(a_pct + p_pct)]))
    style_fig(f, height=max(240, 46 * len(cats)))
    f.update_yaxes(showgrid=False)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

# Health nudges: quiet, plain-language findings — nothing renders when healthy.
# Per person only: with no names on screen, a combined list couldn't say whose
# nudge is whose.
findings = [] if household else compute.health_checks(
    profile, d.income, d.targets, d.contributions, d.adjustments, fmt=inr_short
)
if findings:
    section("Health")
    for finding in findings:
        st.caption(finding)
