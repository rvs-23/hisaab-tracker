"""Allocation page: where the year's investment money goes, in % and ₹.

Merges the old Target and Monthly Plan pages. You set one percentage mix per
instrument (sum to 100); the page shows the resulting ₹/year and ₹/month. The
grid is the page: edit %s, see the rupees, Save.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import inr_short, load_all, metric_tile, page_header, pretty_category

d = load_all()
scope = page_header("Allocation", d.profiles)
selected = [p for p in d.profiles if p.key in scope]
CURRENT_YEAR = dt.date.today().year

income_years = sorted(d.income["year"].dropna().astype(int).unique()) or [CURRENT_YEAR]
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else income_years[-1]
yc, _ = st.columns([1, 5])
year = int(yc.selectbox("Year", income_years, index=income_years.index(default_year)))
st.caption("Where your investment money goes. Set the % per instrument (must sum to 100); the ₹/year and ₹/month follow from that year's investment amount.")


def investment_for(profile):
    row = compute.budget_series(profile, d.income).query("year == @year")
    return float(row.iloc[0]["investment"]) if not row.empty else 0.0


total_year = sum(investment_for(p) for p in selected)
mc = st.columns(3)
metric_tile(mc[0], "To invest this year", inr_short(total_year), f"{year}, across selection", big=True)
metric_tile(mc[1], "Per month", inr_short(total_year / 12), "total", big=True)
st.write("")

for profile in selected:
    st.subheader(profile.name)
    investment = investment_for(profile)
    target = compute.resolve_target(profile, d.targets, year)

    grid = pd.DataFrame({"category": d.config.categories})
    grid["label"] = grid["category"].map(pretty_category)
    grid["pct"] = [target.get(c, 0.0) for c in d.config.categories]
    grid["per_year"] = grid["pct"] / 100 * investment
    grid["per_month"] = grid["per_year"] / 12

    edited = st.data_editor(
        grid[["label", "pct", "per_year", "per_month"]],
        hide_index=True, width="stretch", key=f"alloc_{profile.key}_{year}",
        column_config={
            "label": st.column_config.TextColumn("Instrument", disabled=True),
            "pct": st.column_config.NumberColumn("Target %", min_value=0, max_value=100, required=True),
            "per_year": st.column_config.NumberColumn("₹ / year", disabled=True, format="%.0f"),
            "per_month": st.column_config.NumberColumn("₹ / month", disabled=True, format="%.0f"),
        },
    )
    total_pct = edited["pct"].sum()
    ok = abs(total_pct - 100) < 0.01
    note = f"Total: <b>{total_pct:.0f}%</b>" + ("" if ok else " · must sum to 100 before saving")
    st.markdown(f"<span style='color:{'#0F766E' if ok else '#86198F'}'>{note}</span> · "
                f"investment this year: {inr_short(investment)}", unsafe_allow_html=True)

    if st.button(f"Save {profile.name} · {year}", key=f"save_alloc_{profile.key}_{year}",
                 type="primary", disabled=not ok):
        rows = pd.DataFrame({"profile": profile.key, "year": year,
                             "category": d.config.categories, "pct": edited["pct"].values})
        rows = rows[rows["pct"] > 0]  # store only the categories that get something
        others = d.targets[~((d.targets["profile"] == profile.key) & (d.targets["year"] == year))]
        merged = pd.concat([others, rows], ignore_index=True)
        try:
            storage.validate_targets(merged, d.config, d.profiles)
            storage.save_targets(d.root, merged)
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")
    st.caption(f"A saved year carries forward until you set a newer one.")
