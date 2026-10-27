import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from audit import row_last_changed
from config import EMERGENCY_FUND_MONTHS
from ui import (
    GRID, ON_TRACK_PCT, accent_primary, accent_secondary, chart_title, edit_card,
    inr_axis, inr_short, load_all, metric_tile, page_header,
    pretty_category, save_failed, saved, section, seed_slice_sig, slice_sig,
    stale_since_open, style_fig,
)

d = load_all()
active = page_header("Investments", d.profiles, d.root)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
st.caption("Record what you invested, then see it against the plan.")

if d.income[d.income["profile"] == active.key].empty:
    st.info("No data yet. Add income first.")
    st.stop()
years = compute.selectable_years(d.income, d.contributions, active.key)

default = dt.date.today().year if dt.date.today().year in years else years[-1]
yc, _ = st.columns([1, 5])
year = int(yc.selectbox("Year", years, index=years.index(default)))

def contrib_slice(df):
    """This person's rows for the picked year, from ``df``."""
    return df[(df["profile"] == active.key) & (df["year"] == year)]


with edit_card(f"Record what you invested in {year}"):
    st.caption("One row per instrument with the year's total so far. Add a row with the "
               "+ under the table, or change an amount when you invest more. Then Save.")
    # Scoped like the rest of the page: this person, this year. The key carries
    # both, so pending edits can never leak across a profile or year switch.
    sig_cols = ["category", "amount", "notes"]
    seed_key = f"contrib_{active.key}_{year}_seed"
    mine = contrib_slice(d.contributions).drop(columns=["profile", "year"])
    seed_slice_sig(seed_key, slice_sig(mine, sig_cols))  # what disk held when this grid opened
    # Read-only, from the audit log; never saved (the save keeps CONTRIB_COLUMNS only).
    stamps = row_last_changed(d.root, "contributions.csv", ["profile", "year", "category"])
    mine["updated"] = [
        f"{stamps[(active.key, year, c)]:%-d %b %Y}" if (active.key, year, c) in stamps else ""
        for c in mine["category"]
    ]
    edited = st.data_editor(
        mine.sort_values("category").reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch",
        key=f"contrib_{active.key}_{year}",
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True, format="localized"),
            "notes": "Notes",
            "updated": st.column_config.TextColumn(
                "Last updated", disabled=True,
                help="When this row was last saved, from the audit log. Blank for rows "
                     "entered before the log existed."),
        },
    )
    if st.button("Save contributions", type="primary"):
        try:
            # Re-read fresh so another tab's edit to a *different* slice survives,
            # and bail if *this* slice changed under us (a real conflict).
            fresh = storage.load_contributions(d.root, d.config, d.profiles)
            fresh_mine = contrib_slice(fresh).drop(columns=["profile", "year"])
            if stale_since_open(seed_key, slice_sig(fresh_mine, sig_cols), f"{year}'s contributions"):
                st.stop()
            others = fresh[~((fresh["profile"] == active.key) & (fresh["year"] == year))]
            mine_now = edited.assign(profile=active.key, year=year)
            combined = pd.concat([others, mine_now], ignore_index=True)[storage.CONTRIB_COLUMNS]
            storage.validate_contributions(combined, d.config, d.profiles)
            storage.save_contributions(d.root, combined)
            st.session_state.pop(seed_key, None)
            saved()
        except Exception as exc:
            save_failed(exc)

pva = compute.plan_vs_actual(active, d.income, d.targets, d.contributions, year)
emergency_fund = compute.emergency_fund_target(active, d.income, year)

if pva.empty:
    st.info("No plan for this selection/year yet.")
    st.stop()

chart_title(f"Planned vs actual, by bucket · {year}")
asc = pva.sort_values("expected")
f = go.Figure()
labels = [pretty_category(x) for x in asc["category"]]
gap = [f"{'over' if v >= 0 else 'short'} by {inr_short(abs(v))}" for v in asc["shortfall"]]
f.add_bar(y=labels, x=asc["expected"], name="Planned", orientation="h", marker_color=SECONDARY,
          text=[inr_short(v) for v in asc["expected"]], textposition="outside")
f.add_bar(y=labels, x=asc["actual"], name="Actual", orientation="h", marker_color=PRIMARY,
          text=[inr_short(v) for v in asc["actual"]], textposition="outside",
          customdata=gap, hovertemplate="%{y}: %{text} (%{customdata})<extra></extra>")
f.update_traces(cliponaxis=False)
f.update_layout(barmode="group")
# Headroom so the outside labels on the longest bar stay inside the plot.
inr_axis(f, 1.15 * max(asc["expected"].max(), asc["actual"].max()), axis="x")
style_fig(f)
f.update_xaxes(showgrid=True, gridcolor=GRID)
f.update_yaxes(showgrid=False)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

ef_sub = f"{EMERGENCY_FUND_MONTHS} months of your latest salary up to {year}"
ef_actual = compute.emergency_fund_actual(d.adjustments, active.key)

goal_pct = compute.pct_goal_achieved(pva)
# One tile, goal-and-held together (same shape as the dashboard's plan tile:
# headline the target, actuals on the sub-lines).
ef_status = (
    "not entered yet" if ef_actual == 0
    else "covers the goal" if ef_actual >= emergency_fund
    else f"{inr_short(emergency_fund - ef_actual)} short"
)
section(f"How {year} is tracking")
cols = st.columns(3)
metric_tile(cols[0], "Goal achieved", f"{goal_pct:.0f}%", f"of {year}'s plan",
            color=PRIMARY if goal_pct >= ON_TRACK_PCT else SECONDARY, big=True)
metric_tile(cols[1], "Invested", inr_short(pva["actual"].sum()),
            f"of {inr_short(pva['expected'].sum())} planned", big=True)
metric_tile(cols[2], "Emergency-fund goal", inr_short(emergency_fund),
            f"held: {inr_short(ef_actual)}<br>{ef_status}",
            color=SECONDARY, big=True,
            help=f"The target ({ef_sub}). The sub-line is the buffer you actually "
                 "hold, entered below and counted in your estimated value as cash.")

with st.expander("Update emergency fund"):
    st.caption("The cash/liquid buffer you actually hold. Audited like any other save.")
    new_ef = st.number_input("Emergency fund held (₹)", min_value=0, value=int(ef_actual),
                             step=10000, key=f"ef_{active.key}")
    st.caption(f"= {inr_short(new_ef)}")
    if st.button("Save", key=f"save_ef_{active.key}", type="primary"):
        try:
            fresh = storage.load_adjustments(d.root, d.profiles)
            others = fresh[
                ~((fresh["profile"] == active.key) & (fresh["field"] == "emergency_fund"))
            ]
            rows = pd.DataFrame([{"profile": active.key, "field": "emergency_fund", "value": new_ef}])
            rows = rows[rows["value"] > 0]  # zero means "nothing recorded"
            merged = pd.concat([others, rows], ignore_index=True)[storage.ADJUSTMENTS_COLUMNS]
            storage.validate_adjustments(merged, d.profiles)
            storage.save_adjustments(d.root, merged)
            saved()
        except Exception as exc:
            save_failed(exc)
st.write("")

st.caption(f"The emergency-fund goal above is {EMERGENCY_FUND_MONTHS} months of your salary. What you actually hold goes in the expander above.")
