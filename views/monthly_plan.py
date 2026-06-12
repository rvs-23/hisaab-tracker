import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, page_header

d = load_all()
scope = page_header("Monthly Plan", d.profiles)

CURRENT_YEAR = dt.date.today().year
st.caption(f"What to invest each month in {CURRENT_YEAR}, per instrument — target % × this year's budget ÷ 12.")

selected = [p for p in d.profiles if p.key in scope]
plans = {}
for p in selected:
    expected = compute.expected_contributions(p, d.income, d.targets, CURRENT_YEAR)
    if expected:
        plans[p.name] = pd.Series(expected) / 12

if not plans:
    st.info("No income entered yet — add it on the Income page.")
    st.stop()

table = pd.DataFrame(plans)
if len(plans) > 1:
    table["Combined"] = table.sum(axis=1)
table = table.sort_values(table.columns[-1], ascending=False)

total_monthly = table[table.columns[-1]].sum()
st.metric("Total to invest / month", inr(total_monthly), help="Combined across selected people" if len(plans) > 1 else None)

st.dataframe(
    table.reset_index(names="category"),
    column_config={"category": "Category"} | {
        c: st.column_config.NumberColumn(f"{c} (₹/mo)", format="%.0f") for c in table.columns
    },
    hide_index=True, width="stretch",
)

with st.expander("Yearly equivalents"):
    yearly = table * 12
    st.dataframe(
        yearly.reset_index(names="category"),
        column_config={"category": "Category"} | {
            c: st.column_config.NumberColumn(f"{c} (₹/yr)", format="%.0f") for c in yearly.columns
        },
        hide_index=True, width="stretch",
    )
