import pandas as pd
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, page_header

d = load_all()
scope = page_header("Target allocation", d.profiles)
st.caption("Your target mix, constant across years. Two tiers: short-term for the invested slice of *wants* money, long-term for *investment* money.")

# Per-person by nature — household falls back to the first person.
profile = next((p for p in d.profiles if p.key == scope), None) or d.profiles[0]
if scope is None:
    st.caption(f"Showing {profile.name}'s target. Pick a person in the sidebar to switch.")

left, right = st.columns(2)
for col, (title, mix) in zip(
    (left, right),
    (("Long-term (investment money)", profile.target.long_term),
     (f"Short-term (wants money · {profile.wants_invest_pct:.0f}% invested)", profile.target.short_term)),
):
    with col:
        st.subheader(title)
        s = pd.Series(mix, name="pct").sort_values(ascending=False)
        st.bar_chart(s, horizontal=True, color="#2b2b2b")

# This year's planned rupee amounts per category, from the target × the budget pools.
rows = d.budget[d.budget["profile"] == profile.key]
if rows.empty:
    st.info(f"No budget rows for {profile.name} yet — add them on the Update Data page.")
    st.stop()

year = int(rows["year"].max())
expected = compute.expected_contributions(profile, d.budget, year)
exp_df = (
    pd.DataFrame({"category": expected.keys(), "expected": expected.values()})
    .sort_values("expected", ascending=False)
)
st.subheader(f"Planned amounts — {year}")
st.metric("Total planned investment", inr(exp_df["expected"].sum()))
st.dataframe(
    exp_df,
    column_config={
        "category": "Category",
        "expected": st.column_config.NumberColumn("Planned (₹)", format="%.0f"),
    },
    hide_index=True,
    width="stretch",
)
