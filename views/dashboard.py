import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import grays, inr, load_all, sidebar_scope

root, config, profiles, holdings, income = load_all()
scope = sidebar_scope(profiles)

st.title("Hisaab")

current = compute.current_holdings(holdings)
history = compute.networth_history(holdings, config, profiles)

cols = st.columns(len(profiles) + 1)
cols[0].metric("Household", inr(history["Household"].iloc[-1]))
for col, p in zip(cols[1:], profiles):
    person = compute.to_inr(current[current["profile"] == p.key], config)
    as_of = current.loc[current["profile"] == p.key, "date"].max()
    col.metric(p.name, inr(person["value_inr"].sum()), help=f"as of {as_of:%d %b %Y}")

st.caption(
    f"USD→INR rate {config.usd_inr_rate} (as of {config.usd_inr_as_of:%d %b %Y}) · "
    f"data folder: {root}"
)

# Sidebar selector drives the chart: one person, or all series for the household.
if scope is None:
    chart = history
else:
    name = next(p.name for p in profiles if p.key == scope)
    chart = history[[name]]

st.subheader("Net worth over time")
st.line_chart(chart, color=grays(chart.shape[1]))

with st.expander("Snapshot totals by date"):
    st.dataframe(history.style.format("{:,.0f}"), width="stretch")
