import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, sidebar_scope

root, config, profiles, holdings, income = load_all()
profile_key = sidebar_scope(profiles)

st.title("Current allocation")

alloc = compute.allocation(holdings, config, profile_key)

if alloc.empty:
    st.info("No holdings for this scope yet — add rows on the Update Data page.")
    st.stop()

st.metric("Total", inr(alloc["value_inr"].sum()))

left, right = st.columns([1, 1])
with left:
    st.dataframe(
        alloc,
        column_config={
            "category": "Category",
            "value_inr": st.column_config.NumberColumn("Value (₹)", format="%.0f"),
            "pct": st.column_config.NumberColumn("% of portfolio", format="%.1f%%"),
        },
        hide_index=True,
        width="stretch",
    )
with right:
    st.bar_chart(alloc.set_index("category")["pct"], horizontal=True, color="#2b2b2b")
