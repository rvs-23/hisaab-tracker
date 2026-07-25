"""Rent vs buy: a stateless calculator, not a save.

Compares the two choices as **net cost** — money that left your hands, minus the
asset you ended up owning:

    buying  = registration + loan interest + maintenance − the home's appreciation
    renting = rent paid − the growth on the difference the renter invests

The buyer's down payment and repaid principal are not costs — they become equity
in a home that appreciates. The renter's own savings aren't costs either. So a
low (or negative) bar means the asset grew more than the money spent on it.
Nothing here reads or writes the data CSVs; it's pure what-if.
"""

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
from config import RENTER_INVEST_DISCIPLINE_PCT
from ui import (
    CHART_TEXT, FS_BODY, accent_primary, accent_secondary, chart_title,
    inr_axis, inr_short, load_all, metric_tile, page_header, style_fig,
)

d = load_all()
profile = page_header("Rent vs buy", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()
today_year = dt.date.today().year
k = profile.key  # per-person widget key suffix, so switching profile keeps inputs separate

st.caption(
    "A calculator, not a save — nothing here is written to your data. Both choices are "
    "measured the same way: **net cost** — what you paid out, minus the asset you end up "
    "owning (the buyer's appreciating home, the renter's invested savings). Lower is "
    "better; below zero means the asset outgrew the spend. Every number is overridable."
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
    invest_discipline_pct = st.number_input(
        "Of the difference, actually invested (%)", min_value=0.0, max_value=100.0,
        value=float(RENTER_INVEST_DISCIPLINE_PCT), step=5.0, key=f"rvb_discipline_{k}",
        help="A buyer's EMI is forced saving; a renter with a smaller outgoing tends "
             "to spend part of the gap rather than invest it all. 100% is the "
             "idealised renter who invests every spare rupee.",
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
    horizon_years=horizon_years, invest_discipline_pct=invest_discipline_pct,
)
yr = (today_year - 1 + df["year"]).astype(str)  # calendar years from the locked start

# Net cost, as grouped bars: Buying vs Renting+investing. "Net" = money out minus
# the asset each side builds (the home's appreciation for the buyer, the invested
# difference's growth for the renter). Cumulative by default; per-year shows each
# year on its own so year 1's registration + heavy interest stands out.
chart_title(
    "Net cost — what you spend minus what you own",
    help="Buying: registration + loan interest + maintenance, minus the home's "
         "appreciation (the down payment and repaid principal are equity, not cost). "
         "Renting: rent paid, minus the growth on the difference the renter invests. "
         "Lower is better; a bar below zero means the asset grew more than you spent.",
)
view = st.radio("View", ["Cumulative", "Per year"], horizontal=True,
                label_visibility="collapsed", key=f"rvb_view_{k}")
per_year = view == "Per year"


def shape(col: str):
    """The chart series for ``col``: per-year deltas, or the running total."""
    return df[col].diff().fillna(df[col].iloc[0]) if per_year else df[col]


buy = shape("buy_wasted_net")
rent = shape("rent_wasted_net")

f = go.Figure()
f.add_trace(go.Bar(x=yr, y=buy, name="Buying", marker_color=PRIMARY,
                   hovertemplate="%{x}: ₹%{y:,.0f}<extra>Buying</extra>"))
f.add_trace(go.Bar(x=yr, y=rent, name="Renting + investing the rest", marker_color=SECONDARY,
                   hovertemplate="%{x}: ₹%{y:,.0f}<extra>Renting</extra>"))
f.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06, xaxis=dict(type="category"))
lo = min(buy.min(), rent.min(), 0)
hi = max(buy.max(), rent.max(), 0)
inr_axis(f, hi * 1.08, min_value=lo * 1.08, min_step=25_00_000 if per_year else 1_00_00_000)
style_fig(f, height=460)
# After style_fig — it resets legend and margin. Legend above, left-aligned.
f.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
                margin=dict(l=8, r=8, t=44, b=8))
f.update_yaxes(title_text="Net cost — lower is better", title_font=dict(size=12, color=CHART_TEXT))
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

buy_end = float(df.iloc[-1]["buy_wasted_net"])
rent_end = float(df.iloc[-1]["rent_wasted_net"])
horizon_year = today_year + horizon_years - 1
leaner, gap = (("Buying", rent_end - buy_end) if buy_end <= rent_end
               else ("Renting + investing", buy_end - rent_end))
appr_end = float(df.iloc[-1]["appreciation_gain"])
discipline_note = (f", with the renter investing {invest_discipline_pct:.0f}% of the monthly "
                   "difference" if invest_discipline_pct < 100 else "")
st.caption(
    f"By {horizon_year}, **{leaner.lower()} is ahead by {inr_short(abs(gap))}**{discipline_note}. "
    f"Buying's net cost is {inr_short(buy_end)} — its "
    f"{inr_short(df.iloc[-1]['buy_wasted_cum'])} of registration + interest + maintenance "
    f"less {inr_short(appr_end)} of home appreciation. Renting's is {inr_short(rent_end)} — "
    f"{inr_short(df.iloc[-1]['rent_wasted_cum'])} of rent less the growth on what's invested."
)

# Year by year — the equity story in numbers: the down payment and principal
# build an asset that appreciates, alongside the interest/maintenance that don't.
with st.expander("Year by year — where each rupee goes"):
    table = pd.DataFrame({
        "Year": yr.values,
        "Interest": df["interest_paid"],
        "Principal": df["principal_paid"],
        "Maintenance": df["maintenance_paid"],
        "Loan left": df["loan_balance"],
        "Home equity": df["buy_equity"],
        "Net cost buying": df["buy_wasted_net"],
        "Rent": df["rent_paid"],
        "Net cost renting": df["rent_wasted_net"],
    })
    st.dataframe(
        table.style.format({c: "₹{:,.0f}" for c in table.columns if c != "Year"}),
        width="stretch", hide_index=True,
    )
    first, last = df.iloc[0], df.iloc[-1]
    if first["interest_paid"] > 0:
        st.caption(
            f"Home equity starts at your {inr_short(down_payment)} down payment and grows as "
            f"principal is repaid and the home appreciates — {inr_short(first['buy_equity'])} in "
            f"{yr.iloc[0]} to {inr_short(last['buy_equity'])} by {yr.iloc[-1]}. Interest is "
            f"front-loaded: {inr_short(first['interest_paid'])} vs {inr_short(first['principal_paid'])} "
            f"principal in {yr.iloc[0]}, flipping to {inr_short(last['interest_paid'])} vs "
            f"{inr_short(last['principal_paid'])} by {yr.iloc[-1]}."
        )

# Headline tiles: the cash facts of buying, plus the verdict.
total_interest = monthly_emi * tenure_years * 12 - loan_principal
cols = st.columns(4)
metric_tile(cols[0], "EMI / month", inr_short(monthly_emi), f"{tenure_years}-year loan", big=True)
metric_tile(cols[1], "Total interest", inr_short(total_interest), "over the full tenure", big=True)
metric_tile(cols[2], "Registration cost", inr_short(registration_cost), f"{registration_pct:.1f}% of price", big=True)
metric_tile(cols[3], f"Ahead by {horizon_year}", leaner, f"by {inr_short(abs(gap))}",
            color=PRIMARY, big=True,
            help="The lower net-cost bar at the horizon — money spent minus the asset "
                 "you own. Assumes the renter reinvests the difference.")

st.markdown(
    f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveats. The verdict swings "
    "on the assumptions — appreciation, investment return, rent inflation — so treat it as "
    "illustrative. <b>Ready-to-move-in</b>: rent stops the day you buy, no construction gap "
    "or pre-EMI. Interest follows a real monthly amortization; maintenance, rent and returns "
    "compound yearly. No tax breaks modelled (Section 24/80C, HRA), and no selling or "
    "brokerage costs. Both sides ignore liquidity — a home is far harder to sell than a "
    "portfolio.</div>",
    unsafe_allow_html=True,
)
