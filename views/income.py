import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute, storage
from finance_tracker.ui import TEAL, inr, inr_short, load_all, page_header

d = load_all()
scope = page_header("Income", d.profiles)
selected = [p for p in d.profiles if p.key in scope]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
existing_years = sorted(d.income["year"].dropna().astype(int).unique())
default_year = existing_years[-1] if existing_years else dt.date.today().year

c1, _ = st.columns([1, 3])
year = int(c1.number_input("Year", min_value=2000, max_value=2100, value=int(default_year), step=1))
st.caption("Fill the 12 months for the selected year — salary, bonus, other. Everything else in the app derives from this.")


def annual(profile_key, yr):
    rows = d.income[(d.income["profile"] == profile_key) & (d.income["year"] == yr)]
    return rows[["salary", "bonus", "other"]].sum().sum()


for profile in selected:
    st.subheader(profile.name)
    mine = d.income[(d.income["profile"] == profile.key) & (d.income["year"] == year)]

    grid = pd.DataFrame({"Month": MONTHS, "salary": 0, "bonus": 0, "other": 0})
    if not mine.empty:
        for _, r in mine.iterrows():
            i = int(r["month"]) - 1
            grid.loc[i, ["salary", "bonus", "other"]] = [r["salary"], r["bonus"], r["other"]]
    else:
        # New year: pre-fill salary with last year's monthly average to save typing.
        prev = annual(profile.key, year - 1)
        if prev:
            grid["salary"] = round(prev / 12)
            st.caption(f"Pre-filled salary from {year - 1}'s monthly average — adjust as needed.")

    edited = st.data_editor(
        grid, num_rows="fixed", hide_index=True, width="stretch", key=f"income_{profile.key}_{year}",
        column_config={
            "Month": st.column_config.TextColumn("Month", disabled=True),
            "salary": st.column_config.NumberColumn("Salary (₹)", required=True),
            "bonus": st.column_config.NumberColumn("Bonus (₹)", required=True),
            "other": st.column_config.NumberColumn("Other (₹)", required=True),
        },
    )
    total = (edited["salary"] + edited["bonus"] + edited["other"]).sum()
    prev_total = annual(profile.key, year - 1)
    delta = f"{100 * (total - prev_total) / prev_total:+.0f}% vs {year - 1}" if prev_total else None
    st.metric(f"{year} total income", inr_short(total), delta=delta, delta_color="off")

    if st.button(f"Save {profile.name} · {year}", key=f"save_{profile.key}_{year}", type="primary"):
        new = edited.copy()
        new["profile"] = profile.key
        new["year"] = year
        new["month"] = range(1, 13)
        new = new[storage.INCOME_COLUMNS]
        others = d.income[~((d.income["profile"] == profile.key) & (d.income["year"] == year))]
        merged = pd.concat([others, new], ignore_index=True)
        try:
            storage.validate_income(merged, d.profiles)
            storage.save_income(d.root, merged)
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")

# Income-over-time, all entered years.
visible = d.income[d.income["profile"].isin(scope)]
if not visible.empty and len(visible["year"].unique()) > 1:
    names = {p.key: p.name for p in d.profiles}
    by_year = (
        visible.assign(total=visible["salary"] + visible["bonus"] + visible["other"])
        .groupby(["year", "profile"])["total"].sum().unstack("profile").rename(columns=names)
    )
    st.subheader("Income by year")
    st.bar_chart(by_year, color=TEAL if by_year.shape[1] == 1 else None)
