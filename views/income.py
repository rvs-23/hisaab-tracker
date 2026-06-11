import pandas as pd
import streamlit as st

from finance_tracker.ui import grays, load_all, sidebar_scope

root, config, profiles, holdings, income = load_all()
scope = sidebar_scope(profiles)

st.title("Income")

if income.empty:
    st.info("No income recorded yet — add rows on the Update Data page.")
    st.stop()

names = {p.key: p.name for p in profiles}
if scope is not None:
    income = income[income["profile"] == scope]

st.subheader("Monthly totals")
monthly = (
    income.assign(month=income["date"].dt.to_period("M").dt.to_timestamp())
    .groupby(["month", "profile"])["amount"]
    .sum()
    .unstack("profile")
    .rename(columns=names)
)
if scope is None:
    monthly["Household"] = monthly.sum(axis=1)
st.bar_chart(monthly, color=grays(monthly.shape[1]))

st.subheader("All entries")
st.dataframe(
    income.sort_values("date", ascending=False),
    column_config={
        "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "profile": "Person",
        "source": "Source",
        "amount": st.column_config.NumberColumn("Amount (₹)", format="%.0f"),
        "notes": "Notes",
    },
    hide_index=True,
    width="stretch",
)
