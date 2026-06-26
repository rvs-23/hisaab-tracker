import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from ui import (
    ON_TRACK_PCT, accent_primary, accent_secondary, edit_card, grid_color, html_table,
    inr_short, load_all, metric_tile, page_header, pretty_category, section, style_fig,
)

d = load_all()
active = page_header("Actuals", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
scope = [active.key]
st.caption("What actually went in, against the plan. Planned (mulberry) vs actual (teal) per category; negative shortfall = under-invested.")

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
st.markdown(f"<div style='font-weight:600;font-size:.95rem;color:var(--text);margin:.2rem 0 .4rem'>Planned vs actual, by bucket · {year}</div>", unsafe_allow_html=True)
asc = pva.sort_values("expected")
f = go.Figure()
f.add_bar(y=[pretty_category(x) for x in asc["category"]], x=asc["expected"], name="Planned",
          orientation="h", marker_color=SECONDARY)
f.add_bar(y=[pretty_category(x) for x in asc["category"]], x=asc["actual"], name="Actual",
          orientation="h", marker_color=PRIMARY)
f.update_layout(barmode="group", xaxis=dict(tickprefix="₹", tickformat="~s"))
style_fig(f)
f.update_xaxes(showgrid=True, gridcolor=grid_color())
f.update_yaxes(showgrid=False)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

section(f"How {year} is tracking")
cols = st.columns(3)
metric_tile(cols[0], "Goal achieved", f"{compute.pct_goal_achieved(pva):.0f}%", f"of {year}'s plan",
            color=PRIMARY if compute.pct_goal_achieved(pva) >= ON_TRACK_PCT else SECONDARY, big=True)
metric_tile(cols[1], "Emergency-fund goal", inr_short(emergency_fund), f"6 months of {year} needs", big=True,
            help="Derived, not entered: 6 months of that year's needs bucket (6 × monthly needs).")
st.write("")

ordered = pva.sort_values("expected", ascending=False)
html_table(
    ordered,
    {"category": "Category", "expected": "Planned", "actual": "Actual", "shortfall": "Shortfall / surplus"},
    formats={"category": pretty_category, "expected": inr_short, "actual": inr_short, "shortfall": inr_short},
)

section("Fill in")

def merge_back(edited, others, columns, key):
    """Combines this person's edited rows with the other profiles' untouched rows.

    The page is scoped to one person, so the editors hide the profile column and
    only show ``active``'s rows; on save we stamp the active key back on and keep
    everyone else's rows intact.
    """
    edited = edited.assign(profile=key)
    return pd.concat([others, edited], ignore_index=True)[columns]


with edit_card("Record what you actually invested"):
    st.caption("One row per year / instrument. Add rows as you invest.")
    mine = d.contributions[d.contributions["profile"] == active.key].drop(columns=["profile"])
    edited = st.data_editor(
        mine.sort_values(["year", "category"]).reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch", key="contrib_editor",
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d", required=True),
            "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
    )
    if st.button("Save contributions", type="primary"):
        try:
            others = d.contributions[d.contributions["profile"] != active.key]
            combined = merge_back(edited, others, storage.CONTRIB_COLUMNS, active.key)
            storage.validate_contributions(combined, d.config, d.profiles)
            storage.save_contributions(d.root, combined)
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")

st.caption("The emergency-fund goal above is derived from your budget (6 months of needs), so there's nothing to enter for it.")
