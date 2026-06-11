import streamlit as st

from finance_tracker import storage
from finance_tracker.ui import edit_grid, load_all, page_header

d = load_all()
scope = page_header("Income", d.profiles)
st.caption("Non-salary income (bonus / other). Salary lives in the budget plan.")

edit_grid(
    d.income,
    {
        "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
        "profile": st.column_config.SelectboxColumn("Person", options=[p.key for p in d.profiles], required=True),
        "source": st.column_config.TextColumn("Source", required=True),
        "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
        "notes": "Notes",
    },
    lambda df: storage.validate_income(df, d.profiles),
    storage.save_income,
    d.root, key="income_editor", label="income",
)

income = d.income
if scope is not None:
    income = income[income["profile"] == scope]

if income.empty:
    st.info("No income recorded for this scope yet — add rows on the Update Data page.")
    st.stop()

names = {p.key: p.name for p in d.profiles}

st.subheader("By year")
yearly = (
    income.assign(year=income["date"].dt.year)
    .groupby(["year", "profile"])["amount"]
    .sum()
    .unstack("profile")
    .rename(columns=names)
)
st.bar_chart(yearly, color="#2b2b2b" if yearly.shape[1] == 1 else None)

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
