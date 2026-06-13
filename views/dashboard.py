import altair as alt
import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    INK, MULBERRY, TEAL, inr, inr_short, load_all, metric_tile, page_header, pretty_category,
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


def label(text):
    st.markdown(
        f"<div style='font-size:.75rem;text-transform:uppercase;letter-spacing:.05em;"
        f"color:{GRAY};margin:.5rem 0 .1rem'>{text}</div>",
        unsafe_allow_html=True,
    )


def stats(profiles):
    pva = compute.household_plan_vs_actual(profiles, d.income, d.targets, d.contributions, year)
    target, invested = pva["expected"].sum(), pva["actual"].sum()
    income_yr = invest_yr = 0.0
    for p in profiles:
        row = compute.budget_series(p, d.income).query("year == @year")
        if not row.empty:
            income_yr += row.iloc[0]["total_income"]
            invest_yr += row.iloc[0]["investment"]
    return {
        "target": target, "invested": invested, "remaining": max(target - invested, 0.0),
        "progress": compute.pct_goal_achieved(pva) if not pva.empty else 0.0,
        "rate": 100 * invest_yr / income_yr if income_yr else 0.0,
    }


# --- Goal progress, one card per selected person + household when both --------
label(f"Goal progress · {year}")
entities = [(p.name, [p]) for p in selected]
if len(selected) > 1:
    entities.append(("Household", selected))
for col, (name, profs) in zip(st.columns(len(entities)), entities):
    s = stats(profs)
    color = TEAL if s["progress"] >= ON_TRACK else MULBERRY
    metric_tile(col, name, f"{s['progress']:.0f}%", f"{inr_short(s['invested'])} of {inr_short(s['target'])}",
                color=color, big=True)

# --- This year's numbers -----------------------------------------------------
agg = stats(selected)
ai = compute.annual_income(d.income)
ai = ai[ai["profile"].isin(scope)]
inc_now = ai.query("year == @year")[compute.COMPONENTS].sum().sum()
inc_prev = ai.query("year == @year - 1")[compute.COMPONENTS].sum().sum()
yoy = f"{100 * (inc_now - inc_prev) / inc_prev:+.0f}% vs {year - 1}" if inc_prev else "first year"
left = f"{agg['remaining'] / agg['target'] * 100:.0f}% of target left" if agg["target"] else ""

label(f"This year · {year}")
c = st.columns(4)
metric_tile(c[0], "Income", inr_short(inc_now), yoy)
metric_tile(c[1], "Target", inr_short(agg["target"]), "to invest this year")
metric_tile(c[2], "Still to go", inr_short(agg["remaining"]), left, color=MULBERRY)
metric_tile(c[3], "Per month", inr_short(agg["target"] / 12), "see Monthly Plan")

# --- Actual invested by year (the main graph) --------------------------------
label("Actual invested by year")
contrib = d.contributions[d.contributions["profile"].isin(scope)]
if contrib.empty:
    st.caption("Nothing recorded yet. Add contributions on the Plan vs Actual page.")
else:
    piv = contrib.groupby(["year", "profile"])["amount"].sum().unstack("profile").rename(columns=names)
    order = [p.name for p in selected if p.name in piv.columns]
    piv = piv[order]
    if len(order) > 1:
        piv["Combined"] = piv.sum(axis=1)
    long = piv.reset_index().melt("year", var_name="Who", value_name="amount").dropna()
    series = order + (["Combined"] if len(order) > 1 else [])
    palette = ([TEAL, MULBERRY] * 3)[: len(order)] + ([INK] if len(order) > 1 else [])
    chart = (
        alt.Chart(long)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("year:O", title=None),
            y=alt.Y("amount:Q", title="Invested (₹)", axis=alt.Axis(format="~s")),
            color=alt.Color("Who:N", title=None,
                            scale=alt.Scale(domain=series, range=palette),
                            legend=alt.Legend(orient="top")),
            tooltip=["year", "Who", alt.Tooltip("amount:Q", format=",.0f")],
        )
        .properties(height=300)
        .configure_axis(grid=True, gridColor="#ececec")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, use_container_width=True)

# --- Year on year: salary, investment, savings rate --------------------------
frames = []
for p in selected:
    bs = compute.budget_series(p, d.income)
    if not bs.empty:
        frames.append(bs[~bs["is_projected"]][["year", "total_income", "investment"]])
if frames:
    agg_y = pd.concat(frames).groupby("year", as_index=False)[["total_income", "investment"]].sum().sort_values("year")
    agg_y["sal_g"] = agg_y["total_income"].pct_change() * 100
    agg_y["inv_g"] = agg_y["investment"].pct_change() * 100
    agg_y["rate"] = 100 * agg_y["investment"] / agg_y["total_income"]
    label("Year on year")
    disp = pd.DataFrame({
        "Year": agg_y["year"].astype(int).astype(str),
        "Income": agg_y["total_income"].map(inr),
        "Income +%": agg_y["sal_g"].map(lambda v: "—" if pd.isna(v) else f"{v:+.0f}%"),
        "Investment": agg_y["investment"].map(inr),
        "Investment +%": agg_y["inv_g"].map(lambda v: "—" if pd.isna(v) else f"{v:+.0f}%"),
        "Invest rate": agg_y["rate"].map(lambda v: f"{v:.0f}%"),
    })
    sty = disp.style.set_properties(**{"text-align": "right"}).set_table_styles(
        [{"selector": "th", "props": [("text-align", "right")]}]
    ).hide(axis="index")
    st.dataframe(sty, width="stretch", hide_index=True)

# --- Notes, at the end -------------------------------------------------------
hh = compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, year)
on_track = sum(
    1 for cy in contrib_years
    if compute.pct_goal_achieved(
        compute.household_plan_vs_actual(selected, d.income, d.targets, d.contributions, cy)
    ) >= ON_TRACK
)
notes = [f"On track in {on_track} of {len(contrib_years)} years (75%+ of goal)."]
if not hh.empty:
    worst = hh.loc[hh["shortfall"].idxmin()]
    if worst["shortfall"] < 0:
        notes.append(f"Biggest gap right now is {pretty_category(worst['category'])} ({inr_short(worst['shortfall'])}).")
goals = d.goals[(d.goals["year"] == year) & (d.goals["profile"].isin(scope))]
if not goals.empty:
    notes.append(f"Emergency fund goal for {year} is {inr(goals['emergency_fund_goal'].sum())}.")
invested_to_date = d.contributions[d.contributions["profile"].isin(scope)]["amount"].sum()
notes.append(f"Investing {agg['rate']:.0f}% of income this year, {inr(invested_to_date)} in so far across all years.")

label("Notes")
for n in notes:
    st.caption(n)
