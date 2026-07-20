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

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from config import AFFORD_EMI_CAP_PCT
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
    "Money wasted, cumulative",
    help="Waste = money you never get back. Buying wastes registration + loan interest "
         "+ maintenance — never the principal, which becomes your equity. Renting wastes "
         "the rent. A renter who leaves the difference in idle cash also wastes the growth "
         "they gave up, so that line sits higher. Lower = less wasted.",
)
# Only the Buying line carries value labels — three sets of numbers collided
# into noise. The rest read off the grid, the hover, or the table below.
lines = [
    ("Buying", df["buy_wasted_cum"], PRIMARY, "solid", 3, True),
    ("Renting + investing the difference", df["rent_wasted_cum"], SECONDARY, "solid", 3, False),
    ("Renting, cash left idle", df["rent_wasted_no_invest_cum"], COST_LINE, "dash", 2, False),
]
f = go.Figure()
for name, series, color, dash, width, show_values in lines:
    f.add_trace(go.Scatter(
        x=yr, y=series, name=name, mode="lines+markers+text" if show_values else "lines+markers",
        line=dict(color=color, width=width, dash=dash), marker=dict(size=5),
        text=[inr_short(v) for v in series] if show_values else None,
        textposition="top center", textfont=dict(color=color, size=11),
        cliponaxis=False,
        hovertemplate="%{x}: ₹%{y:,.0f}<extra>" + name + "</extra>",
    ))
# Legend below the plot: above it, it crowded the section title and pushed the
# first year's label off the grid.
f.update_layout(xaxis=dict(type="category"),
                legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
                margin=dict(t=20, b=70))
# Auto step (≈5 round gridlines); a fixed 10L grid gives 16 lines at these
# magnitudes. The 5% headroom keeps the top value label on the canvas.
inr_axis(f, max(s.max() for _, s, *_ in lines) * 1.05)
style_fig(f, height=440)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

buy_end = float(df.iloc[-1]["buy_wasted_cum"])
rent_end = float(df.iloc[-1]["rent_wasted_cum"])
idle_end = float(df.iloc[-1]["rent_wasted_no_invest_cum"])
horizon_year = today_year + horizon_years - 1
leaner, gap = ("Buying", rent_end - buy_end) if buy_end <= rent_end else ("Renting", buy_end - rent_end)
st.caption(
    f"By {horizon_year}, **{leaner.lower()} wastes {inr_short(abs(gap))} less**: buying burns "
    f"{inr_short(buy_end)} (registration + interest + maintenance) against {inr_short(rent_end)} "
    f"of rent. Leaving the difference in idle cash pushes renting's waste to "
    f"{inr_short(idle_end)} — the {inr_short(idle_end - rent_end)} gap is what investing it is worth."
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

# What would it take? One goal, saving from zero: the SIP for the down payment,
# the EMI on the balance, and the salary that keeps that EMI under the cap.
buy_year = today_year + horizon_years
chart_title(
    "What would it take?",
    help="Isolated to this one goal, saving from zero: the monthly SIP to reach the "
         "down payment + registration by the horizon (house price grown at the "
         "appreciation rate), the EMI on the loan, and the salary that keeps the EMI "
         f"under {AFFORD_EMI_CAP_PCT}% of income. Ignores your existing corpus and other goals.",
)
future_price = price * (1 + appreciation_pct / 100) ** horizon_years
upfront_target = future_price * (down_pct + registration_pct) / 100
sip = compute.sip_for_target(upfront_target, invest_return_pct, horizon_years)
loan_then = future_price * (1 - down_pct / 100)
emi_then = compute.emi(loan_then, loan_rate_pct, tenure_years)
salary_needed = emi_then / (AFFORD_EMI_CAP_PCT / 100) if AFFORD_EMI_CAP_PCT else 0.0
wcols = st.columns(3)
metric_tile(wcols[0], "Save / month", inr_short(sip),
            f"to reach {inr_short(upfront_target)} by {buy_year}", color=SECONDARY, big=True)
metric_tile(wcols[1], "EMI after", inr_short(emi_then),
            f"on a {inr_short(loan_then)} loan", big=True)
metric_tile(wcols[2], f"Salary needed, {buy_year}", inr_short(salary_needed),
            f"so EMI ≤ {AFFORD_EMI_CAP_PCT}% of it", color=PRIMARY, big=True)

bs = compute.budget_series(profile, d.income)
entered = bs[~bs["is_projected"]]
monthly_income = float(entered.iloc[-1]["total_income"]) / 12 if not entered.empty else 0.0
cur_row = bs[bs["year"] == today_year]
monthly_investment = float(cur_row.iloc[0]["monthly_investment"]) if not cur_row.empty else 0.0
if monthly_income > 0:
    proj_income = monthly_income * (1 + appreciation_pct / 100) ** horizon_years
    invest_bit = (f"You invest about {inr_short(monthly_investment)}/mo now vs the "
                  f"{inr_short(sip)} this needs. " if monthly_investment > 0 else "")
    st.caption(
        invest_bit
        + f"Your income would be roughly {inr_short(proj_income)}/mo by {buy_year} "
        f"(growing at the appreciation rate) against the {inr_short(salary_needed)} needed."
    )
else:
    st.caption("Add income to see this against your own numbers.")

st.markdown(
    f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveats: this compares "
    "waste, not wealth — the buyer also ends up owning a house, which this chart "
    "deliberately ignores. Interest follows a real monthly amortization; maintenance, "
    "rent and returns compound yearly. No tax breaks modelled (Section 24/80C, HRA), and "
    "no selling or brokerage costs.</div>",
    unsafe_allow_html=True,
)
