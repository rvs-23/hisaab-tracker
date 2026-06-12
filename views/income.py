import streamlit as st

from finance_tracker import storage
from finance_tracker.ui import GRAYS, TEAL, load_all, page_header

d = load_all()
scope = page_header("Income", d.profiles)
st.caption("What came in, per person per year — salary, bonus, other. Everything else derives from this. Edit below and Save.")

names = {p.key: p.name for p in d.profiles}
visible = d.income[d.income["profile"].isin(scope)]

if not visible.empty:
    chart = (
        visible.assign(total=visible["salary"] + visible["bonus"] + visible["other"])
        .groupby(["year", "profile"])["total"].sum().unstack("profile").rename(columns=names)
    )
    st.bar_chart(chart, color=TEAL if chart.shape[1] == 1 else GRAYS[: chart.shape[1]])

# The grid is the page — Excel-style: type a row per person per year, Save.
edited = st.data_editor(
    d.income.sort_values(["profile", "year"]).reset_index(drop=True),
    num_rows="dynamic", hide_index=True, width="stretch", key="income_editor",
    column_config={
        "profile": st.column_config.SelectboxColumn("Person", options=list(names), required=True),
        "year": st.column_config.NumberColumn("Year", format="%d", required=True),
        "salary": st.column_config.NumberColumn("Salary (₹)", required=True),
        "bonus": st.column_config.NumberColumn("Bonus (₹)", required=True),
        "other": st.column_config.NumberColumn("Other (₹)", required=True),
    },
)
if st.button("Save income", type="primary"):
    try:
        storage.validate_income(edited, d.profiles)
        storage.save_income(d.root, edited)
        st.success("Saved.")
        st.rerun()
    except Exception as exc:
        st.error(f"Not saved: {exc}")
