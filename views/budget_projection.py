import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import INK, MULBERRY, TEAL, inr_short, load_all, metric_tile, page_header, style_fig

NEEDS = "#b9c0c7"
CURRENT_YEAR = dt.date.today().year

d = load_all()
scope = page_header("Budget", d.profiles)
st.caption(
    "How income splits, derived from the plan. The anchor year is 50/30/20 "
    "(needs/wants/investment). After that only each year's raise splits 20/30/50, "
    "so the investment slice keeps growing."
)

income_years = sorted(d.income["year"].dropna().astype(int).unique())
if not income_years:
    st.info("No income entered yet. Add it on the Income page.")
    st.stop()
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else income_years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", income_years, index=income_years.index(default_year))

HEADERS = {
    "year": "Year", "age": "Age", "total_income": "Income (₹)",
    "needs": "Needs (₹)", "wants": "Wants (₹)", "investment": "Investment (₹)",
    "monthly_needs": "Needs /mo", "monthly_wants": "Wants /mo",
    "monthly_investment": "Invest /mo", "cumulative_invested": "Cumulative invested",
}
MONEY = ["total_income", "needs", "wants", "investment", "monthly_needs",
         "monthly_wants", "monthly_investment", "cumulative_invested"]


def style_row(row):
    if row["is_projected"]:
        return [f"color: {MULBERRY}; font-style: italic"] * len(row)
    if row["Year"] == CURRENT_YEAR:
        return ["background-color: #E0EFED; font-weight: 600"] * len(row)
    return [""] * len(row)


for profile in (p for p in d.profiles if p.key in scope):
    bs = compute.budget_series(profile, d.income)
    st.subheader(profile.name)
    if bs.empty:
        st.info(f"No income for {profile.name} yet. Add it on the Income page.")
        continue

    # This year's split.
    row = bs[bs["year"] == year]
    if not row.empty:
        r = row.iloc[0]
        pct = compute.split_pct(r)
        cols = st.columns(3)
        metric_tile(cols[0], "Needs", f"{inr_short(r['monthly_needs'])}/mo", f"{pct['needs']:.0f}% of income", color=INK, big=True)
        metric_tile(cols[1], "Wants", f"{inr_short(r['monthly_wants'])}/mo", f"{pct['wants']:.0f}% of income", color=MULBERRY, big=True)
        metric_tile(cols[2], "Investment", f"{inr_short(r['monthly_investment'])}/mo", f"{pct['investment']:.0f}% of income", color=TEAL, big=True)

    # The slice shifting over the actual years (100% stacked).
    actual = bs[~bs["is_projected"]]
    yr = actual["year"].astype(int).astype(str)
    tot = actual["total_income"]
    needs_p = (100 * actual["needs"] / tot).round(0)
    wants_p = (100 * actual["wants"] / tot).round(0)
    inv_p = (100 * actual["investment"] / tot).round(0)
    f = go.Figure()
    f.add_bar(x=yr, y=needs_p, name="Needs", marker_color=NEEDS)
    f.add_bar(x=yr, y=wants_p, name="Wants", marker_color=MULBERRY)
    f.add_bar(x=yr, y=inv_p, name="Investment", marker_color=TEAL,
              text=[f"{v:.0f}%" for v in inv_p], textposition="inside",
              textfont=dict(color="white", size=11), insidetextanchor="middle")
    f.update_layout(barmode="stack", yaxis=dict(ticksuffix="%", range=[0, 100]),
                    title=None)
    style_fig(f, height=300)
    st.markdown("<div style='font-weight:600;font-size:.92rem;color:#3a3a3a;margin:.4rem 0 .4rem'>The investment slice, year by year</div>", unsafe_allow_html=True)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

    with st.expander("Full detail (all years + projections)"):
        table = bs.drop(columns=["invested_this_year"]).rename(columns=HEADERS)
        styled = (
            table.style.apply(style_row, axis=1)
            .format({HEADERS[c]: "{:,.0f}" for c in MONEY})
            .hide(axis="index")
        )
        st.dataframe(styled, width="stretch", column_config={"is_projected": None})
