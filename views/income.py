import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, page_header

d = load_all()
scope = page_header("Income", d.profiles)
st.caption("Annual income per person — salary + bonus + other. Everything else (budget, plan) derives from this.")

income = d.income[d.income["profile"].isin(scope)].copy()

if income.empty:
    st.info("No income for this selection yet — add rows on the Update Data page.")
    st.stop()

income["total"] = income["salary"] + income["bonus"] + income["other"]
names = {p.key: p.name for p in d.profiles}

st.subheader("Total income by year")
by_year = income.groupby(["year", "profile"])["total"].sum().unstack("profile").rename(columns=names)
st.bar_chart(by_year, color="#2b2b2b" if by_year.shape[1] == 1 else None)

latest = income.loc[income["year"].idxmax()]
st.metric(f"Latest income ({int(latest['year'])})", inr(income[income['year'] == latest['year']]['total'].sum()))

st.subheader("All entries")
st.dataframe(
    income.assign(person=income["profile"].map(names)).sort_values(["year", "profile"], ascending=[False, True]),
    column_config={
        "year": st.column_config.NumberColumn("Year", format="%d"),
        "person": "Person",
        "salary": st.column_config.NumberColumn("Salary (₹)", format="%.0f"),
        "bonus": st.column_config.NumberColumn("Bonus (₹)", format="%.0f"),
        "other": st.column_config.NumberColumn("Other (₹)", format="%.0f"),
        "total": st.column_config.NumberColumn("Total (₹)", format="%.0f"),
        "profile": None,
    },
    hide_index=True,
    width="stretch",
)
