"""Target page: set the allocation for the year's investment amount.

A single percentage mix per category (it must sum to 100). The plan for the year
is just that year's derived investment split by these percentages — nothing is
carried from wants. The grid is the page: edit %s, see the rupees, Save.
"""

import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import inr, inr_short, load_all, page_header, pretty_category

d = load_all()
scope = page_header("Target", d.profiles)
CURRENT_YEAR = dt.date.today().year

income_years = sorted(d.income["year"].dropna().astype(int).unique())
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else (income_years[-1] if income_years else CURRENT_YEAR)
yc, _ = st.columns([1, 5])
year = int(yc.selectbox("Year", income_years or [CURRENT_YEAR], index=(income_years or [CURRENT_YEAR]).index(default_year)))
st.caption("Set where the year's investment money goes, in %. Must sum to 100. The ₹ column is that year's investment split by your %s.")

for profile in (p for p in d.profiles if p.key in scope):
    st.subheader(profile.name)

    # This year's investment amount (the pool the %s are applied to).
    bs = compute.budget_series(profile, d.income)
    row = bs[bs["year"] == year]
    investment = float(row.iloc[0]["investment"]) if not row.empty else 0.0
    target = compute.resolve_target(profile, d.targets, year)

    grid = pd.DataFrame(
        {"category": d.config.categories,
         "pct": [target.get(c, 0.0) for c in d.config.categories]}
    )
    grid["label"] = grid["category"].map(pretty_category)
    grid["amount"] = grid["pct"] / 100 * investment

    edited = st.data_editor(
        grid[["label", "pct", "amount"]],
        hide_index=True, width="stretch", key=f"target_{profile.key}_{year}",
        column_config={
            "label": st.column_config.TextColumn("Instrument", disabled=True),
            "pct": st.column_config.NumberColumn("Target %", min_value=0, max_value=100, required=True),
            "amount": st.column_config.NumberColumn("≈ This year (₹)", disabled=True, format="%.0f"),
        },
    )
    total_pct = edited["pct"].sum()
    ok = abs(total_pct - 100) < 0.01
    note = f"Total: **{total_pct:.0f}%**" + ("" if ok else "  ·  must sum to 100 before saving")
    st.markdown(f"<span style='color:{'#0F766E' if ok else '#86198F'}'>{note}</span>  ·  "
                f"investment this year: {inr_short(investment)}", unsafe_allow_html=True)

    if st.button(f"Save {profile.name} · {year}", key=f"save_target_{profile.key}_{year}",
                 type="primary", disabled=not ok):
        rows = pd.DataFrame({
            "profile": profile.key, "year": year,
            "category": d.config.categories, "pct": edited["pct"].values,
        })
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
    st.caption(f"Saved years for {profile.name} carry forward until you set a newer one. Total planned {year}: {inr(investment)}.")
