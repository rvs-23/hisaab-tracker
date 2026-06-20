import datetime as dt

import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import html_table, inr_short, load_all, metric_tile, page_header, pretty_category

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
mc = st.columns([1, 2])
metric_tile(mc[0], "Total to invest / month", inr_short(total_monthly),
            "combined across selection" if len(plans) > 1 else "", big=True)
st.write("")

people_cols = list(table.columns)


def _table(df, suffix):
    headers = {"category": "Category"} | {c: f"{c} {suffix}" for c in people_cols}
    formats = {"category": pretty_category} | {c: inr_short for c in people_cols}
    html_table(df.reset_index(names="category"), headers, formats=formats)


_table(table, "/mo")

with st.expander("Yearly equivalents"):
    _table(table * 12, "/yr")
