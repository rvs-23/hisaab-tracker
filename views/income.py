import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from config import INCOME_COMPONENTS as COMPONENTS
from ui import (
    accent_primary, accent_secondary, edit_card, inr_short, load_all, page_header,
    resync, section, style_fig,
)

d = load_all()
profile = page_header("Income", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
selected = [profile]
scope = [profile.key]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ss = st.session_state

# --- income over time, on top --------------------------------------------
visible = d.income[d.income["profile"].isin(scope)]
if not visible.empty:
    section("Income over time")
    by_year = (
        visible.assign(total=visible[COMPONENTS].sum(axis=1))
        .groupby(["year", "profile"])["total"].sum().unstack("profile")
    )
    yr = by_year.index.astype(int).astype(str)
    f = go.Figure()
    for col in by_year.columns:
        f.add_bar(x=yr, y=by_year[col], name="Income", marker_color=PRIMARY)
    # YoY income growth above each bar, so the raise is visible at a glance.
    year_totals = by_year.sum(axis=1)
    growth = ["" if pd.isna(v) else f"+{v:.0f}%" for v in year_totals.pct_change() * 100]
    f.add_trace(go.Scatter(
        x=yr, y=year_totals, mode="text", text=growth, textposition="top center",
        textfont=dict(size=11, color="#6b7280"), showlegend=False, hoverinfo="skip",
        cliponaxis=False))
    # Mark job-change years with a star above the bar.
    jc = visible.groupby("year")["job_change"].max()
    jc_years = [int(y) for y in jc.index if jc.loc[y] > 0]
    if jc_years:
        totals = visible.assign(t=visible[COMPONENTS].sum(axis=1)).groupby("year")["t"].sum()
        f.add_trace(go.Scatter(
            x=[str(y) for y in jc_years], y=[totals[y] for y in jc_years],
            mode="markers", name="Job change",
            marker=dict(symbol="triangle-down", size=10, color="#64748b", line=dict(width=1, color="white")),
            hovertext="Job change", hoverinfo="text+x"))
    f.update_layout(barmode="stack", xaxis=dict(type="category"),
                    yaxis=dict(tickprefix="₹", tickformat="~s"))
    style_fig(f, height=280)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

section("Enter income")
st.caption("Pick a year and fill the 12 months. Salary, bonus, and anything else (RSU vesting, an FD or RD maturing) under Other.")

this_year = dt.date.today().year
year_options = compute.selectable_years(d.income, d.contributions, profile.key)
default_year = this_year if this_year in year_options else year_options[-1]
c1, _ = st.columns([1, 3])
year = int(c1.selectbox("Year", year_options, index=year_options.index(default_year)))


def annual(profile_key, yr):
    rows = d.income[(d.income["profile"] == profile_key) & (d.income["year"] == yr)]
    return rows[COMPONENTS].sum().sum()


def saved_job_change(profile_key, yr):
    rows = d.income[(d.income["profile"] == profile_key) & (d.income["year"] == yr)]
    return bool(rows["job_change"].max()) if not rows.empty else False


def fresh_grid(profile_key, yr):
    grid = pd.DataFrame({"Month": MONTHS})
    for component in COMPONENTS:
        grid[component] = 0
    mine = d.income[(d.income["profile"] == profile_key) & (d.income["year"] == yr)]
    if not mine.empty:
        for _, r in mine.iterrows():
            grid.loc[int(r["month"]) - 1, COMPONENTS] = [r[c] for c in COMPONENTS]
    elif annual(profile_key, yr - 1):  # new year: carry last year's monthly salary
        grid["salary"] = round(annual(profile_key, yr - 1) / 12)
    grid["Total"] = grid[COMPONENTS].sum(axis=1)
    return grid


for profile in selected:
    with edit_card(f"Enter {year}"):
        base = f"inc_{profile.key}_{year}"
        gkey, vkey = f"{base}_grid", f"{base}_ver"
        if gkey not in ss:
            ss[gkey] = fresh_grid(profile.key, year)
            ss[vkey] = 0

        edited = st.data_editor(
            ss[gkey], num_rows="fixed", hide_index=True, width="stretch",
            key=f"{base}_{ss[vkey]}",
            column_config={
                "Month": st.column_config.TextColumn("Month", disabled=True),
                "salary": st.column_config.NumberColumn("Salary (₹)", required=True),
                "bonus": st.column_config.NumberColumn("Bonus (₹)", required=True),
                "other": st.column_config.NumberColumn("Other (₹)", required=True),
                "Total": st.column_config.NumberColumn("Total (₹)", disabled=True),
            },
        )
        # Recompute the (disabled) Total live as the user types.
        resync(gkey, vkey, edited.assign(Total=edited[COMPONENTS].sum(axis=1)), ["Total"])

        job_change = st.checkbox("Job change this year?", value=saved_job_change(profile.key, year),
                                 key=f"{base}_jc")
        filled = int((edited[COMPONENTS].sum(axis=1) > 0).sum())
        total = edited[COMPONENTS].sum().sum()
        prev_total = annual(profile.key, year - 1)
        delta = f"{100 * (total - prev_total) / prev_total:+.0f}% vs {year - 1}" if prev_total else "first year"

        b1, b2, b3 = st.columns([1, 1, 2])
        if b1.button("Copy January down", key=f"{base}_cpy", help="Fill every month with January's values."):
            jan = edited.iloc[0]
            g = edited.copy()
            for c in COMPONENTS:
                g[c] = jan[c]
            ss[gkey] = g.assign(Total=g[COMPONENTS].sum(axis=1))
            ss[vkey] += 1
            st.rerun()
        if b2.button("Save", key=f"{base}_save", type="primary"):
            new = edited[COMPONENTS].copy()
            new["profile"], new["year"], new["month"] = profile.key, year, range(1, 13)
            new["job_change"] = int(job_change)
            new = new[storage.INCOME_COLUMNS]
            others = d.income[~((d.income["profile"] == profile.key) & (d.income["year"] == year))]
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
