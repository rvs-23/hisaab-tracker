"""Allocation page: where the year's investment money goes, in % and ₹.

Merges the old Target and Monthly Plan pages. You set one percentage mix per
instrument (sum to 100); the page shows the resulting ₹/year and ₹/month. The
grid is the page: edit %s, see the rupees, Save.
"""

import datetime as dt

import pandas as pd
import streamlit as st

import compute
import storage
from ui import (
    accent_primary, accent_secondary, edit_card, inr_short, load_all, metric_tile,
    page_header, pretty_category, resync, section,
)

d = load_all()
active = page_header("Allocation", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
selected = [active]
ss = st.session_state
CURRENT_YEAR = dt.date.today().year

income_years = compute.selectable_years(d.income, d.contributions, active.key)
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else income_years[-1]
yc, _ = st.columns([1, 5])
year = int(yc.selectbox("Year", income_years, index=income_years.index(default_year)))


def investment_for(profile):
    row = compute.budget_series(profile, d.income).query("year == @year")
    return float(row.iloc[0]["investment"]) if not row.empty else 0.0


section(f"Investment to deploy · {year}")
total_year = sum(investment_for(p) for p in selected)
mc = st.columns(3)
metric_tile(mc[0], "This year", inr_short(total_year), "across selection", big=True)
metric_tile(mc[1], "Per month", inr_short(total_year / 12), "to invest", big=True)

section("Set your allocation")
st.caption("Set the % per instrument (must sum to 100). The ₹/year and ₹/month follow from that year's investment.")

for profile in selected:
    investment = investment_for(profile)
    target = compute.resolve_target(profile, d.targets, year)

    def derive(df):  # recompute the ₹ columns from the % column
        out = df.copy()
        out["per_year"] = out["pct"] / 100 * investment
        out["per_month"] = out["per_year"] / 12
        return out

    base = f"alloc_{profile.key}_{year}"
    gkey, vkey = f"{base}__grid", f"{base}__ver"
    if gkey not in ss:
        g = pd.DataFrame({"category": d.config.categories})
        g["label"] = g["category"].map(pretty_category)
        g["pct"] = [target.get(c, 0.0) for c in d.config.categories]
        ss[gkey] = derive(g[["label", "pct"]].assign(per_year=0.0, per_month=0.0))
        ss[vkey] = 0

    with edit_card(f"Allocation — {year}"):
        edited = st.data_editor(
            ss[gkey], hide_index=True, width="stretch", key=f"{base}__{ss[vkey]}",
            column_config={
                "label": st.column_config.TextColumn("Instrument", disabled=True),
                "pct": st.column_config.NumberColumn("Target %", min_value=0, max_value=100, required=True),
                "per_year": st.column_config.NumberColumn("₹ / year", disabled=True, format="%.0f"),
                "per_month": st.column_config.NumberColumn("₹ / month", disabled=True, format="%.0f"),
            },
        )
        resync(gkey, vkey, derive(edited), ["per_year", "per_month"])
        total_pct = edited["pct"].sum()
        ok = abs(total_pct - 100) < 0.01
        msg = f"Total <b>{total_pct:.0f}%</b>" + ("  ·  ready to save" if ok else "  ·  must sum to 100")
        st.markdown(f"<span style='color:{PRIMARY if ok else SECONDARY};font-weight:600'>{msg}</span>",
                    unsafe_allow_html=True)

        if st.button(f"Save {year}", key=f"save_alloc_{profile.key}_{year}",
                     type="primary", disabled=not ok):
            rows = pd.DataFrame({"profile": profile.key, "year": year,
                                 "category": d.config.categories, "pct": edited["pct"].values})
            rows = rows[rows["pct"] > 0]
            others = d.targets[~((d.targets["profile"] == profile.key) & (d.targets["year"] == year))]
            merged = pd.concat([others, rows], ignore_index=True)
            try:
                storage.validate_targets(merged, d.config, d.profiles)
                storage.save_targets(d.root, merged)
                del ss[gkey]
                st.success("Saved.")
                st.rerun()
            except Exception as exc:
                st.error(f"Not saved: {exc}")
        st.caption("A saved year carries forward until you set a newer one.")
