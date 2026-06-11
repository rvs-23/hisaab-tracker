import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import inr, load_all

root, config, profiles, holdings, income = load_all()

st.title("Dashboard")

current = compute.current_holdings(holdings)
history = compute.networth_history(holdings, config, profiles)

cols = st.columns(len(profiles) + 1)
cols[0].metric("Household net worth", inr(history["Household"].iloc[-1]))
for col, p in zip(cols[1:], profiles):
    person = compute.to_inr(current[current["profile"] == p.key], config)
    as_of = current.loc[current["profile"] == p.key, "date"].max()
    col.metric(p.name, inr(person["value_inr"].sum()), help=f"as of {as_of:%d %b %Y}")

st.caption(
    f"USD→INR rate {config.usd_inr_rate} (as of {config.usd_inr_as_of:%d %b %Y}) · "
    f"data folder: {root}"
)

st.subheader("Net worth over time")
st.line_chart(history)

with st.expander("Snapshot totals by date"):
    st.dataframe(history.style.format("{:,.0f}"), use_container_width=True)
