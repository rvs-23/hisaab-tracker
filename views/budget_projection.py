import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all, page_header

d = load_all()
scope = page_header("Budget & projection", d.profiles)

st.caption(
    "Budget is derived from income: anchor year splits 50/30/20, then each year only "
    "the income *increment* splits 20/30/50 (invest more as you earn more)."
)

selected = [p for p in d.profiles if p.key in scope]

for profile in selected:
    proj = compute.projection(profile, d.income)
    if proj.empty:
        st.subheader(profile.name)
        st.info(f"No income rows for {profile.name} yet.")
        continue

    latest = proj.iloc[-1]
    pct = compute.split_pct(latest)
    st.subheader(f"{profile.name} — {int(latest['year'])}")
    cols = st.columns(4)
    cols[0].metric("Income / mo", inr(latest["total_income"] / 12))
    cols[1].metric(f"Needs ({pct['needs']:.0f}%)", inr(latest["monthly_needs"]))
    cols[2].metric(f"Wants ({pct['wants']:.0f}%)", inr(latest["monthly_wants"]))
    cols[3].metric(f"Investment ({pct['investment']:.0f}%)", inr(latest["monthly_investment"]))

    st.line_chart(proj.set_index("year")["cumulative_invested"], color="#2b2b2b")
    st.dataframe(
        proj,
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "age": "Age",
            "total_income": st.column_config.NumberColumn("Income (₹)", format="%.0f"),
            "monthly_needs": st.column_config.NumberColumn("Needs /mo (₹)", format="%.0f"),
            "monthly_wants": st.column_config.NumberColumn("Wants /mo (₹)", format="%.0f"),
            "monthly_investment": st.column_config.NumberColumn("Invest /mo (₹)", format="%.0f"),
            "invested_this_year": st.column_config.NumberColumn("Invested in year (₹)", format="%.0f"),
            "cumulative_invested": st.column_config.NumberColumn("Cumulative (₹)", format="%.0f"),
        },
        hide_index=True,
        width="stretch",
    )
