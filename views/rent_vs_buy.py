"""Rent vs buy: a stateless calculator, not a save.

Frames the decision as **money wasted** — cash that buys nothing lasting:

    buying  = registration + loan interest + maintenance
    renting = rent paid (plus forgone growth, if the difference sits idle)

Loan principal is never waste (it becomes equity) and neither are a renter's
own savings (they stay theirs), so both are excluded. Interest comes from a
real monthly amortization schedule, which is why it dominates the early years.
Nothing here reads or writes the data CSVs; it's pure what-if, anchored to the
active person's real numbers.
"""

import datetime as dt
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from config import EMI_SHARE_OF_NEEDS_WANTS_PCT
from ui import (
    COST_LINE, FS_BODY, MARKER, accent_primary, accent_secondary, chart_title,
    inr_axis, inr_short, load_all, metric_tile, page_header, style_fig,
)

d = load_all()
profile = page_header("Rent vs buy", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()
today_year = dt.date.today().year
k = profile.key  # per-person widget key suffix, so switching profile keeps inputs separate

st.caption(
    "A calculator, not a save — nothing here is written to your data. Both sides are "
    "measured the same way: **money wasted**, meaning cash that buys you nothing lasting. "
    "Equity and savings are yours, so they never count as waste. Every number is overridable."
)

target = compute.resolve_target(profile, d.targets, today_year)
default_return = round(compute.expected_return_for_target(target, d.config.expected_return_pct), 1)
return_source = ("the household expected_return_pct in config.yaml"
                 if d.config.expected_return_pct is not None
                 else "your target allocation's weighted expected return")

sc1, sc2, _ = st.columns([1, 1, 2])
sc1.number_input("Start year (locked)", value=today_year, disabled=True, key=f"rvb_start_{k}",
                 help="Scenarios start from the current year; the chart reads in calendar years.")
horizon_years = int(sc2.number_input("Horizon (years)", min_value=1, value=15, step=1, key=f"rvb_horizon_{k}"))

house_col, loan_col, renting_col, invest_col = st.columns(4)

with house_col, st.container(border=True):
    st.markdown("**The house**")
    price = st.number_input("Property price (₹)", min_value=0, value=15_000_000, step=100_000, key=f"rvb_price_{k}")
    st.caption(f"= {inr_short(price)}")
    registration_pct = st.number_input("Registration + stamp duty (% of price)", min_value=0.0, value=7.0, step=0.5, key=f"rvb_reg_{k}")
    maintenance_pct = st.number_input("Maintenance (% of price / yr)", min_value=0.0, value=0.5, step=0.1, key=f"rvb_maint_{k}")
    appreciation_pct = st.number_input("Appreciation (% p.a.)", min_value=0.0, value=5.0, step=0.5, key=f"rvb_appr_{k}")

with loan_col, st.container(border=True):
    st.markdown("**The loan**")
    down_pct = st.slider("Down payment (%)", 0, 100, 20, key=f"rvb_down_{k}")
    st.caption(f"= {inr_short(price * down_pct / 100)}")
    loan_rate_pct = st.number_input("Loan rate (% p.a.)", min_value=0.0, value=8.5, step=0.1, key=f"rvb_rate_{k}")
    tenure_years = int(st.number_input("Tenure (years)", min_value=1, value=20, step=1, key=f"rvb_tenure_{k}"))

with renting_col, st.container(border=True):
    st.markdown("**Renting**")
    rent_monthly = st.number_input("Starting rent (₹ / month)", min_value=0, value=40_000, step=1_000, key=f"rvb_rent_{k}")
    st.caption(f"= {inr_short(rent_monthly)}/mo")
    rent_inflation_pct = st.number_input("Rent inflation (% p.a.)", min_value=0.0, value=5.0, step=0.5, key=f"rvb_rentinfl_{k}")

with invest_col, st.container(border=True):
    st.markdown("**Investing**")
    st.caption("What a renter does with the money buying would have consumed.")
    invest_return_pct = st.number_input(
        "Investment return (% p.a.)", min_value=0.0, value=default_return, step=0.1,
        key=f"rvb_return_{k}",
        help=f"Defaults to {return_source} ({default_return:.1f}%) — the same number "
             "behind the dashboard's Est. value today. Edit to model something else.",
    )

# Derived once, up front — tiles and chart reuse the same numbers as the model.
down_payment = price * down_pct / 100
loan_principal = price - down_payment
registration_cost = price * registration_pct / 100
monthly_emi = compute.emi(loan_principal, loan_rate_pct, tenure_years)

df = compute.rent_vs_buy(
    price=price, down_pct=down_pct, loan_rate_pct=loan_rate_pct, tenure_years=tenure_years,
    registration_pct=registration_pct, maintenance_pct=maintenance_pct,
    appreciation_pct=appreciation_pct, rent_monthly=rent_monthly,
    rent_inflation_pct=rent_inflation_pct, invest_return_pct=invest_return_pct,
    horizon_years=horizon_years,
)
yr = (today_year - 1 + df["year"]).astype(str)  # calendar years from the locked start

# The one chart: cumulative money wasted — cash that bought nothing lasting.
# Everything here stays positive and rising, so "lower line wastes less" reads
# straight off the page. Assets (equity, appreciation, a portfolio) are not
# waste and are deliberately absent; the table below shows where the money went.
chart_title(
    "Money wasted",
    help="Waste = money you never get back. Buying wastes registration + loan interest "
         "+ maintenance — never the principal, which becomes your equity. Renting wastes "
         "the rent. A renter who leaves the difference in idle cash also wastes the growth "
         "they gave up. Lower = less wasted. Per year shows each year on its own "
         "(registration lands once, in year 1); cumulative is the running total.",
)
view = st.radio("View", ["Cumulative", "Per year"], horizontal=True,
                label_visibility="collapsed", key=f"rvb_view_{k}")
# Per-year is the difference of the running totals, keeping year 1 whole —
# cumulative hides the shape (year 1 carries registration and the heaviest
# interest, so it towers over every year after it).
per_year = view == "Per year"


def shape(col: str):
    """The chart series for ``col``: per-year deltas, or the running total."""
    return df[col].diff().fillna(df[col].iloc[0]) if per_year else df[col]
# Three lines. Only Buying carries value labels — three sets of numbers
# collided into noise; the rest read off the grid and the hover.
series = {
    "buy": shape("buy_wasted_cum"),
    "rent": shape("rent_wasted_cum"),
    "idle": shape("rent_wasted_no_invest_cum"),
}
# Three labels only — start, middle, end. Any more and the line disappears
# behind its own numbers; every other year is one hover away.
labelled = {0, (len(df) - 1) // 2, len(df) - 1}

f = go.Figure()
f.add_trace(go.Scatter(
    x=yr, y=series["buy"], name="Buying", mode="lines+markers+text",
    line=dict(color=PRIMARY, width=3), marker=dict(size=5),
    text=[inr_short(v) if i in labelled else "" for i, v in enumerate(series["buy"])],
    textposition="top center",
    textfont=dict(color=PRIMARY, size=11), cliponaxis=False,
    hovertemplate="%{x}: ₹%{y:,.0f}<extra>Buying</extra>",
))
f.add_trace(go.Scatter(
    x=yr, y=series["rent"], name="Renting + investing the rest", mode="lines+markers",
    line=dict(color=SECONDARY, width=3), marker=dict(size=5),
    hovertemplate="%{x}: ₹%{y:,.0f}<extra>Renting, difference invested</extra>",
))
f.add_trace(go.Scatter(
    x=yr, y=series["idle"], name="Renting, rest sits idle", mode="lines",
    line=dict(color=COST_LINE, width=2, dash="dash"),
    hovertemplate="%{x}: ₹%{y:,.0f}<extra>Renting, difference left idle</extra>",
))
f.update_layout(xaxis=dict(type="category"))
# Gridlines in whole 25L multiples: 25L itself where the values are small (per
# year), rounding up to 50L/1Cr as they grow, so the cumulative axis doesn't end
# up with twenty lines.
top = max(s.max() for s in series.values()) * 1.08
step = max(25_00_000, math.ceil(top / 6.5 / 25_00_000) * 25_00_000)
inr_axis(f, top, step=step)
style_fig(f, height=440)
# After style_fig — it sets both legend and margin, so anything set before it is
# silently overwritten. Legend sits above the plot, left-aligned (the names are
# too long to hang off the right edge); l/r margins stay 8 so the plot spans the
# full width.
f.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                margin=dict(l=8, r=8, t=44, b=8))
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

buy_end = float(df.iloc[-1]["buy_wasted_cum"])
rent_end = float(df.iloc[-1]["rent_wasted_cum"])
idle_end = float(df.iloc[-1]["rent_wasted_no_invest_cum"])
horizon_year = today_year + horizon_years - 1
leaner, gap = (("Buying", rent_end - buy_end) if buy_end <= rent_end
               else ("Renting + investing", buy_end - rent_end))
st.caption(
    f"By {horizon_year}, **{leaner.lower()} wastes {inr_short(abs(gap))} less**: buying burns "
    f"{inr_short(buy_end)} (registration + interest + maintenance) against {inr_short(rent_end)} "
    f"of rent. Letting the rest sit idle instead of investing it pushes renting's waste to "
    f"{inr_short(idle_end)} — the {inr_short(idle_end - rent_end)} gap is what the investing is worth."
)

# Year by year, in rupees — the chart's numbers as a table, and the only place
# the EMI split is visible. Early years are almost all interest (pure waste);
# principal overtakes it only well into the tenure.
with st.expander("Year by year — where each rupee goes"):
    table = pd.DataFrame({
        "Year": yr.values,
        "Interest": df["interest_paid"],
        "Principal": df["principal_paid"],
        "Maintenance": df["maintenance_paid"],
        "Loan left": df["loan_balance"],
        "Wasted buying": df["buy_wasted_cum"],
        "Rent": df["rent_paid"],
        "Wasted renting": df["rent_wasted_cum"],
    })
    st.dataframe(
        table.style.format({c: "₹{:,.0f}" for c in table.columns if c != "Year"}),
        width="stretch", hide_index=True,
    )
    first, last = df.iloc[0], df.iloc[-1]
    if first["interest_paid"] > 0:
        st.caption(
            f"Interest is front-loaded because the bank charges it on the outstanding "
            f"balance each month: in {yr.iloc[0]} you pay {inr_short(first['interest_paid'])} "
            f"interest against only {inr_short(first['principal_paid'])} principal "
            f"({100 * first['interest_paid'] / (first['interest_paid'] + first['principal_paid']):.0f}% "
            f"of the EMI is waste); by {yr.iloc[-1]} that flips to "
            f"{inr_short(last['interest_paid'])} interest vs {inr_short(last['principal_paid'])} principal."
        )

# Headline tiles: the three cash facts of buying, plus the verdict.
total_interest = monthly_emi * tenure_years * 12 - loan_principal
cols = st.columns(4)
metric_tile(cols[0], "EMI / month", inr_short(monthly_emi), f"{tenure_years}-year loan", big=True)
metric_tile(cols[1], "Total interest", inr_short(total_interest), "over the full tenure", big=True)
metric_tile(cols[2], "Registration cost", inr_short(registration_cost), f"{registration_pct:.1f}% of price", big=True)
metric_tile(cols[3], f"Wastes less by {horizon_year}", leaner, f"by {inr_short(abs(gap))}",
            color=PRIMARY, big=True,
            help="The lower waste line at the horizon, against a renter who invests the "
                 "difference. Says nothing about which side ends up with more assets.")

# Affordability, from the budget rather than gross income: an EMI is funded out
# of needs + wants (a home replaces rent and squeezes discretionary spend), and
# should never eat the investment slice. The share is yours to set.
chart_title(
    "What you can afford",
    help="Your budget's needs + wants for the current year, not gross income — the "
         "investment slice stays untouched. The share below is how much of that "
         "envelope a home loan may consume; the rest keeps paying for everything "
         "else you need and want.",
)
bs = compute.budget_series(profile, d.income)
entered = bs[~bs["is_projected"]]
monthly_income = float(entered.iloc[-1]["total_income"]) / 12 if not entered.empty else 0.0
cur_row = bs[bs["year"] == today_year]

if not cur_row.empty and monthly_income > 0:
    row = cur_row.iloc[0]
    monthly_needs = float(row["monthly_needs"])
    monthly_wants = float(row["monthly_wants"])
    monthly_investment = float(row["monthly_investment"])
    envelope = monthly_needs + monthly_wants

    share_pct = st.slider(
        "Share of needs + wants an EMI may take (%)", 10, 100,
        EMI_SHARE_OF_NEEDS_WANTS_PCT, step=5, key=f"rvb_emishare_{k}",
    )
    emi_budget = envelope * share_pct / 100
    max_loan = compute.max_loan_for_emi(emi_budget, loan_rate_pct, tenure_years)
    # The loan is (100 − down_pct) of the price, so the price it supports is the
    # loan grossed back up. At 100% down there's no loan to size.
    max_price = max_loan / (1 - down_pct / 100) if down_pct < 100 else 0.0

    acols = st.columns(4)
    metric_tile(acols[0], "Needs + wants / month", inr_short(envelope),
                f"{inr_short(monthly_needs)} needs + {inr_short(monthly_wants)} wants", big=True)
    metric_tile(acols[1], "EMI you can carry", inr_short(emi_budget),
                f"{share_pct}% of that envelope", color=SECONDARY, big=True)
    metric_tile(acols[2], "Loan it supports", inr_short(max_loan),
                f"{loan_rate_pct:.1f}% over {tenure_years} years", big=True)
    metric_tile(acols[3], "House you can buy", inr_short(max_price),
                f"at {down_pct}% down", color=PRIMARY, big=True)

    verdict = ("within reach" if monthly_emi <= emi_budget else "beyond that budget")
    share_of_envelope = 100 * monthly_emi / envelope if envelope else 0.0
    afford_caption = (
        f"This {inr_short(price)} house needs a {inr_short(monthly_emi)} EMI — "
        f"{share_of_envelope:.0f}% of your needs + wants, so it's **{verdict}**. "
    )
    if monthly_emi > emi_budget:
        afford_caption += (
            f"Closing the gap means {inr_short(monthly_emi - emi_budget)} a month more, "
            f"which comes out of the {inr_short(monthly_investment)} you currently invest "
            "unless income grows first."
        )
    else:
        afford_caption += (
            f"That leaves {inr_short(emi_budget - monthly_emi)} a month of the envelope "
            f"spare, with the {inr_short(monthly_investment)} investment slice untouched."
        )
    st.caption(afford_caption)
else:
    st.caption("Add this year's income to see what your budget can carry.")

st.markdown(
    f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveats: this compares "
    "waste, not wealth — the buyer also ends up owning a house, which this chart "
    "deliberately ignores. Interest follows a real monthly amortization; maintenance, "
    "rent and returns compound yearly. No tax breaks modelled (Section 24/80C, HRA), and "
    "no selling or brokerage costs.</div>",
    unsafe_allow_html=True,
)
