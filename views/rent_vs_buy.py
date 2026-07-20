"""Rent vs buy: a stateless calculator, not a save.

Frames the decision the way the household actually thinks about it — money
*wasted*, not net worth — then gives the apples-to-apples verdict as one
line: buyer's assets minus renter's assets (both sides spend the same
housing budget, so the asset gap is the whole answer). Nothing on this page
reads or writes the data CSVs; it's pure what-if, anchored to the active
person's real numbers.
"""

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import compute
from config import AFFORD_EMI_CAP_PCT
from ui import (
    COST_LINE, FS_BODY, MARKER, accent_primary, accent_secondary, chart_title,
    inr_axis, inr_short, load_all, metric_tile, page_header, section, style_fig,
)

d = load_all()
profile = page_header("Rent vs buy", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()
today_year = dt.date.today().year
k = profile.key  # per-person widget key suffix, so switching profile keeps inputs separate

st.caption(
    "A calculator, not a save — nothing here is written to your data. It frames both "
    "choices as **money wasted**, then gives the verdict in one line: whose assets end "
    "up ahead. Defaults and context come from your own data; every number is overridable."
)

target = compute.resolve_target(profile, d.targets, today_year)
default_return = round(compute.expected_return_for_target(target, d.config.expected_return_pct), 1)
return_source = ("the household expected_return_pct in config.yaml"
                 if d.config.expected_return_pct is not None
                 else "your target allocation's weighted expected return")

section("Your numbers")
sc1, sc2, _ = st.columns([1, 1, 2])
sc1.number_input("Start year (locked)", value=today_year, disabled=True, key=f"rvb_start_{k}",
                 help="Scenarios start from the current year; the charts read in calendar years.")
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

# Derived once, up front — the summary, tiles, and charts all reuse the same
# numbers as the model (no separate recompute path).
down_payment = price * down_pct / 100
loan_principal = price - down_payment
registration_cost = price * registration_pct / 100
monthly_emi = compute.emi(loan_principal, loan_rate_pct, tenure_years)
maintenance_annual = price * maintenance_pct / 100

bs = compute.budget_series(profile, d.income)
entered = bs[~bs["is_projected"]]
monthly_income = float(entered.iloc[-1]["total_income"]) / 12 if not entered.empty else 0.0
opening = compute.opening_corpus(d.adjustments, profile.key)
ef_held = compute.emergency_fund_actual(d.adjustments, profile.key) or None
_, nw_potential = compute.net_worth_to_date(
    profile, d.income, d.contributions, d.targets, today_year, opening=opening,
    emergency_fund=ef_held, flat_return=d.config.expected_return_pct,
)

df = compute.rent_vs_buy(
    price=price, down_pct=down_pct, loan_rate_pct=loan_rate_pct, tenure_years=tenure_years,
    registration_pct=registration_pct, maintenance_pct=maintenance_pct,
    appreciation_pct=appreciation_pct, rent_monthly=rent_monthly,
    rent_inflation_pct=rent_inflation_pct, invest_return_pct=invest_return_pct,
    horizon_years=horizon_years,
)
yr = (today_year - 1 + df["year"]).astype(str)  # calendar years from the locked start

# 1. Money wasted — the raw philosophy: cash that bought nothing lasting.
chart_title(
    "Money wasted, cumulative",
    help="Waste = money that buys you nothing lasting. Buying wastes registration + loan "
         "interest + maintenance; renting wastes the rent itself. Assets and their growth "
         "are the next chart's job.",
)
f = go.Figure()
f.add_trace(go.Scatter(x=yr, y=df["buy_wasted_cum"], name="Buying", mode="lines+markers",
                       line=dict(color=PRIMARY, width=3)))
f.add_trace(go.Scatter(x=yr, y=df["rent_wasted_cum"], name="Renting", mode="lines+markers",
                       line=dict(color=MARKER, width=3)))
f.update_layout(xaxis=dict(type="category"))
inr_axis(f, max(df["buy_wasted_cum"].max(), df["rent_wasted_cum"].max()))
style_fig(f, height=320)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})
st.caption("Principal repaid and a renter's invested savings are never counted as waste.")

# 1b. The apples-to-apples verdict as ONE line: buying's assets minus
# renting's assets (both sides spend the same housing budget, so the asset
# difference IS the net advantage). Above zero = buying ahead.
chart_title(
    "Who ends up ahead — buying minus renting",
    help="One line: the buyer's assets (equity + appreciation) minus the renter's "
         "(invested savings + growth), year by year. Both sides spend the same housing "
         "budget, so this difference is the whole verdict. Above zero: buying is ahead.",
)
advantage = df["buy_net"] - df["rent_net"]
advantage_no_invest = df["buy_net"] - df["renter_contributed"]
invest_worth = float(df.iloc[-1]["renter_gain"])
f_adv = go.Figure()
f_adv.add_trace(go.Scatter(x=yr, y=advantage, name="vs renter who invests", mode="lines+markers",
                           line=dict(color=PRIMARY, width=3), fill="tozeroy"))
f_adv.add_trace(go.Scatter(x=yr, y=advantage_no_invest, name="vs renter who doesn't",
                           mode="lines", line=dict(color=MARKER, width=2, dash="dash")))
f_adv.update_layout(xaxis=dict(type="category"), showlegend=True)
inr_axis(f_adv, max(advantage.max(), advantage_no_invest.max(), 0),
         min_value=min(advantage.min(), advantage_no_invest.min(), 0))
style_fig(f_adv, height=300)
st.plotly_chart(f_adv, width="stretch", config={"displayModeBar": False})

adv_caption = ("Above the zero line, buying has you ahead. The dashed line is the verdict "
               "against a renter who leaves the difference as cash — the gap between the "
               f"two lines is what investing the difference is worth: {inr_short(invest_worth)} "
               "by the horizon.")
ahead = advantage >= 0
if not ahead.iloc[0] and ahead.any():
    adv_caption += f" Buying pulls ahead of the investing renter from {int(yr.iloc[ahead.idxmax()])}."
elif ahead.iloc[0] and not ahead.all():
    adv_caption += f" The investing renter pulls ahead from {int(yr.iloc[(~ahead).idxmax()])}."
st.caption(adv_caption)

# 2. Headline tiles.
total_interest = monthly_emi * tenure_years * 12 - loan_principal
adv_end = advantage.iloc[-1]
cols = st.columns(4)
metric_tile(cols[0], "EMI / month", inr_short(monthly_emi), f"{tenure_years}-year loan", big=True)
metric_tile(cols[1], "Total interest", inr_short(total_interest), "over the full tenure", big=True)
metric_tile(cols[2], "Registration cost", inr_short(registration_cost), f"{registration_pct:.1f}% of price", big=True)
metric_tile(cols[3], "Ahead at horizon", "Buying" if adv_end >= 0 else "Renting",
            f"by {inr_short(abs(adv_end))}", color=PRIMARY, big=True,
            help="The verdict line's last point: whose assets are larger at the horizon, "
                 "and by how much.")

# 3. When can you afford it? The affordable price is min(cash, income): early
# you're cash-limited (can't fund the down payment), later income-limited (EMI
# capped). Corpus = investable net worth (excl. emergency fund) growing at the
# invest-return, topped up monthly; income grows at the appreciation rate.
chart_title(
    "When can you afford it?",
    help=f"Two ceilings, whichever is lower: how much house your corpus can put "
         f"down (down payment + registration), and how much your income can "
         f"service (EMI ≤ {AFFORD_EMI_CAP_PCT}% of monthly income). Corpus is your "
         "investable net worth growing at the investment return, topped up by "
         "your monthly investment; income grows at the appreciation rate.",
)
cur_row = bs[bs["year"] == today_year]
monthly_investment = float(cur_row.iloc[0]["monthly_investment"]) if not cur_row.empty else 0.0
investable = max(0.0, nw_potential - (ef_held or 0.0))  # emergency fund stays reserved
if monthly_income > 0:
    aff = compute.affordability_series(
        monthly_income=monthly_income, income_growth_pct=appreciation_pct, price=price,
        appreciation_pct=appreciation_pct, down_pct=down_pct, registration_pct=registration_pct,
        loan_rate_pct=loan_rate_pct, tenure_years=tenure_years, horizon_years=horizon_years,
        emi_cap_pct=AFFORD_EMI_CAP_PCT, starting_corpus=investable,
        monthly_investment=monthly_investment, invest_return_pct=invest_return_pct,
    )
    ax = (today_year + aff["year_offset"]).astype(str)
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=ax, y=aff["house_price"], name="This house", mode="lines+markers",
                            line=dict(color=SECONDARY, width=3)))
    f2.add_trace(go.Scatter(x=ax, y=aff["affordable_price"], name="You can afford", mode="lines+markers",
                            line=dict(color=PRIMARY, width=3)))
    f2.add_trace(go.Scatter(x=ax, y=aff["cash_limited_price"], name="Cash ceiling (down payment)",
                            mode="lines", line=dict(color=COST_LINE, width=1.5, dash="dot")))
    f2.add_trace(go.Scatter(x=ax, y=aff["income_limited_price"], name="Income ceiling (EMI)",
                            mode="lines", line=dict(color=MARKER, width=1.5, dash="dash")))
    f2.update_layout(xaxis=dict(type="category"))
    inr_axis(f2, max(aff["house_price"].max(), aff["affordable_price"].max()))
    style_fig(f2, height=340)
    st.plotly_chart(f2, width="stretch", config={"displayModeBar": False})

    crossing = aff[aff["affordable_price"] >= aff["house_price"]]
    if aff.iloc[0]["affordable_price"] >= aff.iloc[0]["house_price"]:
        afford_caption = "Affordable today — both ceilings clear this house."
    elif not crossing.empty:
        afford_caption = f"You cross into affordability in {today_year + int(crossing.iloc[0]['year_offset'])}."
    else:
        afford_caption = ("Never crosses in this horizon — income growing at the appreciation rate "
                          "keeps the gap open; only raises that outpace the property market close it.")
    # Name the binding constraint today and the year it flips (cash → income).
    binding_now = aff.iloc[0]["binding"]
    flip = aff[aff["binding"] != binding_now]
    afford_caption += (f" Right now you're **{binding_now}-limited** "
                       f"({'saving the down payment' if binding_now == 'cash' else 'servicing the EMI'} is the bottleneck)")
    if not flip.empty:
        afford_caption += f", flipping to {flip.iloc[0]['binding']}-limited in {today_year + int(flip.iloc[0]['year_offset'])}"
    afford_caption += f". Today you can afford about {inr_short(aff.iloc[0]['affordable_price'])}."
    st.caption(afford_caption)
else:
    st.caption("Add income to see affordability.")

# 4. The bottom line, in plain sentences against the person's own numbers.
section("The bottom line")
if monthly_income > 0:
    dp_nw = f" ({100 * (down_payment + registration_cost) / nw_potential:.0f}% of your est. net worth)" if nw_potential > 0 else ""
    st.markdown(
        f"**If you buy today** — down payment + registration is "
        f"**{inr_short(down_payment + registration_cost)}**{dp_nw}; monthly EMI is "
        f"**{inr_short(monthly_emi)}** ({100 * monthly_emi / monthly_income:.0f}% of your monthly take-home)."
    )
    st.markdown(
        f"**If you continue renting** — rent is **{inr_short(rent_monthly)}/mo** "
        f"({100 * rent_monthly / monthly_income:.0f}% of your monthly take-home)."
    )
else:
    st.caption("Add income to see the bottom line against your own numbers.")

st.markdown(
    f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveats: the verdict "
    "line's assumptions — appreciation, investment return, rent inflation — dominate it; "
    "treat it as illustrative. Yearly compounding, not monthly. No tax breaks modelled "
    "(Section 24/80C, HRA). No selling or transaction costs. The affordable price assumes "
    "the down payment is available.</div>",
    unsafe_allow_html=True,
)
