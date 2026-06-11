import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import load_all, sidebar_scope

root, config, profiles, holdings, income = load_all()
profile_key = sidebar_scope(profiles)

st.title("Plan vs actual")
st.caption("Target mix comes from `target_mix` in config.yaml. Positive diff = surplus, negative = shortfall.")

pva = compute.plan_vs_actual(holdings, config, profile_key)

if pva.empty:
    st.info("No holdings for this scope yet — add rows on the Update Data page.")
    st.stop()

st.dataframe(
    pva,
    column_config={
        "category": "Category",
        "target_pct": st.column_config.NumberColumn("Target %", format="%.1f%%"),
        "actual_pct": st.column_config.NumberColumn("Actual %", format="%.1f%%"),
        "target_inr": st.column_config.NumberColumn("Target (₹)", format="%.0f"),
        "actual_inr": st.column_config.NumberColumn("Actual (₹)", format="%.0f"),
        "diff_inr": st.column_config.NumberColumn("Surplus / shortfall (₹)", format="%.0f"),
    },
    hide_index=True,
    width="stretch",
)

st.subheader("Surplus / shortfall by category")
st.bar_chart(pva.set_index("category")["diff_inr"], horizontal=True, color="#2b2b2b")
