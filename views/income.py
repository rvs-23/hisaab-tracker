import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from config import INCOME_COMPONENTS as COMPONENTS
from ui import (
    CHART_TEXT, MARKER, accent_primary, accent_secondary, edit_card, inr_axis,
    inr_short, load_all, page_header, resync, section, style_fig,
)

d = load_all()
active = page_header("Income", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ss = st.session_state

# Income over time, on top.
visible = d.income[d.income["profile"] == active.key]
if not visible.empty:
    section("Income over time")
    totals = visible.assign(total=visible[COMPONENTS].sum(axis=1)).groupby("year")["total"].sum()
    yr = totals.index.astype(int).astype(str)
    f = go.Figure()
    f.add_bar(x=yr, y=totals, name="Income", marker_color=PRIMARY)
    # YoY income growth above each bar, so the raise is visible at a glance.
    growth = ["" if pd.isna(v) else f"+{v:.0f}%" for v in totals.pct_change() * 100]
    f.add_trace(go.Scatter(
        x=yr, y=totals, mode="text", text=growth, textposition="top center",
        textfont=dict(size=11, color=CHART_TEXT), showlegend=False, hoverinfo="skip",
        cliponaxis=False))
    # Mark job-change years with a marker above the bar.
    jc = visible.groupby("year")["job_change"].max()
    jc_years = [int(y) for y in jc.index if jc.loc[y] > 0]
    if jc_years:
        f.add_trace(go.Scatter(
            x=[str(y) for y in jc_years], y=[totals[y] for y in jc_years],
            mode="markers", name="Job change",
            marker=dict(symbol="triangle-down", size=10, color=MARKER, line=dict(width=1, color="white")),
            hovertext="Job change", hoverinfo="text+x"))
    f.update_layout(xaxis=dict(type="category"))
    inr_axis(f, totals.max())
    style_fig(f, height=280)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

section("Enter income")
st.caption("Pick a year and fill the 12 months. Salary, bonus, and anything else (RSU vesting, an FD or RD maturing) under Other.")

this_year = dt.date.today().year
year_options = compute.selectable_years(d.income, d.contributions, active.key)
default_year = this_year if this_year in year_options else year_options[-1]
c1, _ = st.columns([1, 3])
year = int(c1.selectbox("Year", year_options, index=year_options.index(default_year)))


def annual(yr):
    rows = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]
    return rows[COMPONENTS].sum().sum()


def saved_job_change(yr):
    rows = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]
    return bool(rows["job_change"].max()) if not rows.empty else False


def fresh_grid(yr):
    grid = pd.DataFrame({"Month": MONTHS})
    for component in COMPONENTS:
        grid[component] = 0
    mine = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr)]
    prev = d.income[(d.income["profile"] == active.key) & (d.income["year"] == yr - 1)]
    if not mine.empty:
        for _, r in mine.iterrows():
            grid.loc[int(r["month"]) - 1, COMPONENTS] = [r[c] for c in COMPONENTS]
    elif not prev.empty and prev["salary"].sum():
        # New year: carry only last year's salary — a bonus or one-off "other"
        # isn't a recurring monthly amount.
        grid["salary"] = round(prev["salary"].sum() / 12)
    grid["Total"] = grid[COMPONENTS].sum(axis=1)
    return grid


with edit_card(f"Enter {year}"):
    base = f"inc_{active.key}_{year}"
    gkey, vkey = f"{base}_grid", f"{base}_ver"
    if gkey not in ss:
        ss[gkey] = fresh_grid(year)
        ss[vkey] = 0

    edited = st.data_editor(
        ss[gkey], num_rows="fixed", hide_index=True, width="stretch",
        key=f"{base}_{ss[vkey]}",
        column_config={
            "Month": st.column_config.TextColumn("Month", disabled=True),
            "salary": st.column_config.NumberColumn("Salary (₹)", required=True, format="localized"),
            "bonus": st.column_config.NumberColumn("Bonus (₹)", required=True, format="localized"),
            "other": st.column_config.NumberColumn("Other (₹)", required=True, format="localized"),
            "Total": st.column_config.NumberColumn("Total (₹)", disabled=True, format="localized"),
        },
    )
    # Recompute the (disabled) Total live as the user types.
    resync(gkey, vkey, edited.assign(Total=edited[COMPONENTS].sum(axis=1)), ["Total"])

    job_change = st.checkbox("Job change this year?", value=saved_job_change(year),
                             key=f"{base}_jc")
    filled = int((edited[COMPONENTS].sum(axis=1) > 0).sum())
    total = edited[COMPONENTS].sum().sum()
    prev_total = annual(year - 1)
    delta = f"{100 * (total - prev_total) / prev_total:+.0f}% vs {year - 1}" if prev_total else "first year"

    b2, b3 = st.columns([1, 3])
    if b2.button("Save", key=f"{base}_save", type="primary"):
        new = edited[COMPONENTS].copy()
        new["profile"], new["year"], new["month"] = active.key, year, range(1, 13)
        new["job_change"] = int(job_change)
        new = new[storage.INCOME_COLUMNS]
        others = d.income[~((d.income["profile"] == active.key) & (d.income["year"] == year))]
        merged = pd.concat([others, new], ignore_index=True)
        try:
            storage.validate_income(merged, d.profiles)
            storage.save_income(d.root, merged)
            del ss[gkey]
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")
    b3.markdown(
        f"<div style='padding-top:.4rem;color:var(--muted)'>{filled} of 12 months entered &nbsp;·&nbsp; "
        f"<b style='color:var(--text)'>{inr_short(total)}</b> for {year} ({delta})</div>",
        unsafe_allow_html=True,
    )
