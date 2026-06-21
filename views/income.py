import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import storage
from finance_tracker.config import INCOME_COMPONENTS as COMPONENTS
from finance_tracker.ui import (
    MULBERRY, TEAL, edit_card, inr_short, load_all, page_header, section, style_fig,
)

d = load_all()
scope = page_header("Income", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
names = {p.key: p.name for p in d.profiles}
ss = st.session_state

# --- income over time, on top --------------------------------------------
visible = d.income[d.income["profile"].isin(scope)]
if not visible.empty:
    section("Income over time")
    by_year = (
        visible.assign(total=visible[COMPONENTS].sum(axis=1))
        .groupby(["year", "profile"])["total"].sum().unstack("profile").rename(columns=names)
    )
    yr = by_year.index.astype(int).astype(str)
    accents = [TEAL, MULBERRY]
    f = go.Figure()
    for i, col in enumerate(by_year.columns):
        f.add_bar(x=yr, y=by_year[col], name=col, marker_color=accents[i % 2])
    f.update_layout(barmode="stack", yaxis=dict(tickprefix="₹", tickformat="~s"))
    style_fig(f, height=280)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

section("Enter income")
st.caption("Pick a year and fill the 12 months. Salary, bonus, and anything else (RSU vesting, an FD or RD maturing) under Other.")

existing_years = sorted(d.income["year"].dropna().astype(int).unique())
default_year = existing_years[-1] if existing_years else dt.date.today().year
c1, _ = st.columns([1, 3])
year = int(c1.number_input("Year", min_value=2000, max_value=2100, value=int(default_year), step=1))


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
    with edit_card(f"{profile.name} · {year}"):
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
        # Keep the (disabled) Total in sync with edits for the next render.
        ss[gkey] = edited.assign(Total=edited[COMPONENTS].sum(axis=1))

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
