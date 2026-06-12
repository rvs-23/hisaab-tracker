import datetime as dt

import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import MULBERRY, load_all, page_header

d = load_all()
scope = page_header("Budget", d.profiles)
st.caption(
    "How income splits — derived, nothing to enter. Anchor year is 50/30/20 "
    "(needs/wants/investment); after that only each year's income *increment* "
    "splits 20/30/50, so raises mostly go to investing. "
    f":violet[Projected rows] assume {d.profiles[0].forward_increment_pct:.0f}% income growth."
)

CURRENT_YEAR = dt.date.today().year
MONEY = [
    "total_income", "needs", "wants", "investment",
    "monthly_needs", "monthly_wants", "monthly_investment", "cumulative_invested",
]
HEADERS = {
    "year": "Year", "age": "Age", "total_income": "Income (₹)",
    "needs": "Needs (₹)", "wants": "Wants (₹)", "investment": "Investment (₹)",
    "monthly_needs": "Needs /mo", "monthly_wants": "Wants /mo",
    "monthly_investment": "Invest /mo", "cumulative_invested": "Cumulative invested",
}


def style_row(row):
    if row["is_projected"]:
        return [f"color: {MULBERRY}; font-style: italic"] * len(row)
    if row["Year"] == CURRENT_YEAR:
        return ["background-color: #E0EFED; font-weight: 600"] * len(row)
    return [""] * len(row)


for profile in (p for p in d.profiles if p.key in scope):
    bs = compute.budget_series(profile, d.income)
    st.subheader(profile.name)
    if bs.empty:
        st.info(f"No income entered for {profile.name} yet — add it on the Income page.")
        continue
    table = bs.drop(columns=["invested_this_year"]).rename(columns=HEADERS)
    styled = (
        table.style.apply(style_row, axis=1)
        .format({HEADERS[c]: "{:,.0f}" for c in MONEY})
        .hide(axis="index")
    )
    st.dataframe(styled, width="stretch", column_config={"is_projected": None})
