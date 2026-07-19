import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from ui import (
    GRID, ON_TRACK_PCT, accent_primary, accent_secondary, chart_title, edit_card,
    html_table, inr_axis, inr_short, load_all, metric_tile, page_header,
    pretty_category, section, style_fig,
)

d = load_all()
active = page_header("Actuals", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
scope = [active.key]
st.caption("What actually went in, against the plan, per category; negative shortfall = under-invested.")

if d.income[d.income["profile"] == active.key].empty:
    st.info("No data yet — add income first.")
    st.stop()
years = compute.selectable_years(d.income, d.contributions, active.key)

contrib_years = sorted(
    d.contributions.loc[d.contributions["profile"] == active.key, "year"].dropna().astype(int).unique()
)
default = contrib_years[-1] if contrib_years else years[-1]
yc, _ = st.columns([1, 5])
year = int(yc.selectbox("Year", years, index=years.index(default)))

pva = compute.plan_vs_actual(active, d.income, d.targets, d.contributions, year)
emergency_fund = compute.emergency_fund_target(active, d.income, year)

if pva.empty:
    st.info("No plan for this selection/year yet.")
    st.stop()

# Graph first: planned vs actual per bucket.
chart_title(f"Planned vs actual, by bucket · {year}")
asc = pva.sort_values("expected")
f = go.Figure()
f.add_bar(y=[pretty_category(x) for x in asc["category"]], x=asc["expected"], name="Planned",
          orientation="h", marker_color=SECONDARY)
f.add_bar(y=[pretty_category(x) for x in asc["category"]], x=asc["actual"], name="Actual",
          orientation="h", marker_color=PRIMARY)
f.update_layout(barmode="group")
inr_axis(f, max(asc["expected"].max(), asc["actual"].max()), axis="x")
style_fig(f)
f.update_xaxes(showgrid=True, gridcolor=GRID)
f.update_yaxes(showgrid=False)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

# The tile label must say which year the derived buffer really uses: with no
# budget row for the picked year, emergency_fund_target falls back to the
# latest earning year.
bs = compute.budget_series(active, d.income)
has_budget_row = not bs[(bs["year"] == year) & (~bs["is_projected"])].empty
ef_sub = f"6 months of {year} needs" if has_budget_row else "6 months of latest year's needs"

goal_pct = compute.pct_goal_achieved(pva)
section(f"How {year} is tracking")
cols = st.columns(3)
metric_tile(cols[0], "Goal achieved", f"{goal_pct:.0f}%", f"of {year}'s plan",
            color=PRIMARY if goal_pct >= ON_TRACK_PCT else SECONDARY, big=True)
metric_tile(cols[1], "Invested", inr_short(pva["actual"].sum()),
            f"of {inr_short(pva['expected'].sum())} planned", big=True)
metric_tile(cols[2], "Emergency-fund goal", inr_short(emergency_fund), ef_sub, big=True,
            help="Derived, not entered: 6 months of that year's needs bucket (6 × monthly needs).")
st.write("")

ordered = pva.sort_values("expected", ascending=False)
html_table(
    ordered,
    {"category": "Category", "expected": "Planned", "actual": "Actual", "shortfall": "Shortfall / surplus"},
    formats={"category": pretty_category, "expected": inr_short, "actual": inr_short, "shortfall": inr_short},
)

section("Fill in")

with edit_card(f"Record what you actually invested in {year}"):
    st.caption("One row per instrument. Add rows as you invest; other years are untouched.")
    # Scoped like the rest of the page: this person, this year. The key carries
    # both, so pending edits can never leak across a profile or year switch.
    mine = d.contributions[
        (d.contributions["profile"] == active.key) & (d.contributions["year"] == year)
    ].drop(columns=["profile", "year"])
    edited = st.data_editor(
        mine.sort_values("category").reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch",
        key=f"contrib_{active.key}_{year}",
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
    )
    if st.button("Save contributions", type="primary"):
        try:
            # Everyone else's rows and this person's other years stay untouched.
            others = d.contributions[
                ~((d.contributions["profile"] == active.key) & (d.contributions["year"] == year))
            ]
            mine_now = edited.assign(profile=active.key, year=year)
            combined = pd.concat([others, mine_now], ignore_index=True)[storage.CONTRIB_COLUMNS]
            storage.validate_contributions(combined, d.config, d.profiles)
            storage.save_contributions(d.root, combined)
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")

st.caption("The emergency-fund goal above is derived from your budget (6 months of needs), so there's nothing to enter for it.")
