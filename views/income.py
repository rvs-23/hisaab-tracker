import streamlit as st

from finance_tracker.ui import load_all, sidebar_scope

d = load_all()
scope = sidebar_scope(d.profiles)

st.title("Income")
st.caption("Non-salary income (bonus / other). Salary lives in the budget plan.")

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
