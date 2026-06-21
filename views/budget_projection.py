import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from finance_tracker import compute
from finance_tracker.ui import (
    MULBERRY, NEEDS, TEAL, html_table, inr_short, load_all, metric_tile, page_header, section, style_fig,
)

CURRENT_YEAR = dt.date.today().year

d = load_all()
scope = page_header("Budget", d.profiles)
st.caption(
    "How income splits, derived from the plan. The anchor year is 50/30/20 "
    "(needs/wants/investment). After that only each year's raise splits 20/30/50, "
    "so the investment slice keeps growing."
)
st.markdown(
    "<div style='border-left:3px solid #b9c0c7;background:#f7f8f9;border-radius:4px;"
    "padding:.5rem .8rem;color:#555;font-size:.85rem;margin:.2rem 0 .4rem'>"
    "Nothing to fill here — these figures are <b>derived</b>. To change them, edit "
    "<b>Income</b>.</div>",
    unsafe_allow_html=True,
)

income_years = sorted(d.income["year"].dropna().astype(int).unique())
if not income_years:
    st.info("No income entered yet. Add it on the Income page.")
    st.stop()
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else income_years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", income_years, index=income_years.index(default_year))

HEADERS = {
    "year": "Year", "age": "Age", "total_income": "Income", "yoy": "YoY",
    "job_change": "Job change", "needs": "Needs", "wants": "Wants",
    "investment": "Investment", "monthly_needs": "Needs /mo",
    "monthly_wants": "Wants /mo", "monthly_investment": "Invest /mo",
    "cumulative_invested": "Cumulative",
}
MONEY = ["total_income", "needs", "wants", "investment", "monthly_needs",
         "monthly_wants", "monthly_investment", "cumulative_invested"]
FMT = {c: (lambda v: f"{v:,.0f}") for c in MONEY}
FMT["year"] = lambda v: f"{int(v)}"
FMT["age"] = lambda v: f"{int(v)}"
FMT["yoy"] = lambda v: "—" if v is None or pd.isna(v) else f"{v:+.0f}%"
FMT["job_change"] = lambda v: "Yes" if v else ""


def row_class(r):
    if r["is_projected"]:
        return "proj"
    return "cur" if int(r["year"]) == CURRENT_YEAR else ""


# People with data first, so an empty placeholder profile doesn't sit on top.
visible = sorted((p for p in d.profiles if p.key in scope),
                 key=lambda p: compute.budget_series(p, d.income).empty)
for profile in visible:
    bs = compute.budget_series(profile, d.income)
    st.subheader(profile.name)
    if bs.empty:
        st.caption(f"No income for {profile.name} yet. Add it on the Income page.")
        continue

    # This year's split.
    row = bs[bs["year"] == year]
    if not row.empty:
        r = row.iloc[0]
        pct = compute.split_pct(r)
        section(f"Monthly split · {year}")
        cols = st.columns(3)
        metric_tile(cols[0], "Needs", f"{inr_short(r['monthly_needs'])}/mo", f"{pct['needs']:.0f}% of income", big=True)
        metric_tile(cols[1], "Wants", f"{inr_short(r['monthly_wants'])}/mo", f"{pct['wants']:.0f}% of income", color=MULBERRY, big=True)
        metric_tile(cols[2], "Investment", f"{inr_short(r['monthly_investment'])}/mo", f"{pct['investment']:.0f}% of income", color=TEAL, big=True)

    # The slice shifting over the actual years (100% stacked), with the
    # investment segment labelled with both its % and the raw yearly rupees.
    actual = bs[~bs["is_projected"]]
    yr = actual["year"].astype(int).astype(str)
    tot = actual["total_income"]
    needs_p = (100 * actual["needs"] / tot).round(0)
    wants_p = (100 * actual["wants"] / tot).round(0)
    inv_p = (100 * actual["investment"] / tot).round(0)
    inv_label = [f"{p:.0f}% · {inr_short(a)}" for p, a in zip(inv_p, actual["investment"])]
    f = go.Figure()
    f.add_bar(x=yr, y=needs_p, name="Needs", marker_color=NEEDS)
    f.add_bar(x=yr, y=wants_p, name="Wants", marker_color=MULBERRY)
    f.add_bar(x=yr, y=inv_p, name="Investment", marker_color=TEAL,
              text=inv_label, textposition="inside",
              textfont=dict(color="white", size=11), insidetextanchor="middle")
    f.update_layout(barmode="stack", yaxis=dict(ticksuffix="%", range=[0, 100]))
    style_fig(f, height=300)
    st.markdown("<div style='font-weight:600;font-size:.92rem;color:var(--text);margin:.4rem 0 .4rem'>The investment slice, year by year (label shows % and ₹/yr invested)</div>", unsafe_allow_html=True)
    st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

    with st.expander("Full detail (all years + projections)"):
        st.caption("Current year highlighted; projected years in muted italics.")
        html_table(bs, HEADERS, formats=FMT, row_class=row_class)
