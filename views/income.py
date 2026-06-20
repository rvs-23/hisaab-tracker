import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import storage
from finance_tracker.ui import MULBERRY, TEAL, inr_short, load_all, page_header, style_fig

d = load_all()
scope = page_header("Income", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
COMPONENTS = ["salary", "bonus", "rsu", "other"]
names = {p.key: p.name for p in d.profiles}
ss = st.session_state

# --- income over time, on top --------------------------------------------
visible = d.income[d.income["profile"].isin(scope)]
if not visible.empty:
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

st.divider()
st.caption("Fill the 12 months for a year. Salary, bonus, RSU, and anything else like an FD or RD maturing.")

existing_years = sorted(d.income["year"].dropna().astype(int).unique())
default_year = existing_years[-1] if existing_years else dt.date.today().year
c1, _ = st.columns([1, 3])
year = int(c1.number_input("Year", min_value=2000, max_value=2100, value=int(default_year), step=1))


def annual(profile_key, yr):
    rows = d.income[(d.income["profile"] == profile_key) & (d.income["year"] == yr)]
    return rows[COMPONENTS].sum().sum()


def fresh_grid(profile_key, yr):
    grid = pd.DataFrame({"Month": MONTHS, "salary": 0, "bonus": 0, "rsu": 0, "other": 0})
    mine = d.income[(d.income["profile"] == profile_key) & (d.income["year"] == yr)]
    if not mine.empty:
        for _, r in mine.iterrows():
            grid.loc[int(r["month"]) - 1, COMPONENTS] = [r[c] for c in COMPONENTS]
    else:  # new year: carry last year's monthly salary so flat years need no typing
        prev = annual(profile_key, yr - 1)
        if prev:
            grid["salary"] = round(prev / 12)
    return grid


for profile in selected:
    st.subheader(profile.name)
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
            "rsu": st.column_config.NumberColumn("RSU (₹)", required=True),
            "other": st.column_config.NumberColumn("Other (₹)", required=True),
        },
    )
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
        ss[gkey] = g
        ss[vkey] += 1
        st.rerun()
    if b2.button("Save", key=f"{base}_save", type="primary"):
        new = edited.copy()
        new["profile"], new["year"], new["month"] = profile.key, year, range(1, 13)
        new = new[storage.INCOME_COLUMNS]
        others = d.income[~((d.income["profile"] == profile.key) & (d.income["year"] == year))]
        try:
            storage.validate_income(pd.concat([others, new], ignore_index=True), d.profiles)
            storage.save_income(d.root, pd.concat([others, new], ignore_index=True))
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
