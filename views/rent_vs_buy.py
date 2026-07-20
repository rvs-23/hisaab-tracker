"""Rent vs buy: a stateless calculator, not a save.

Frames the decision the way the household actually thinks about it — money
*wasted*, not net worth — made apples-to-apples by netting each side's waste
against the asset that side ends up holding (the buyer's appreciation, the
renter's investment growth). Nothing on this page reads or writes the data
CSVs; it's pure what-if, anchored to the active person's real numbers.
"""

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import compute
from config import AFFORD_EMI_CAP_PCT
from ui import (
    FS_BODY, MARKER, accent_primary, accent_secondary, chart_title, inr_axis,
    inr_short, load_all, metric_tile, page_header, section, style_fig,
)

d = load_all()
profile = page_header("Rent vs buy", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()
today_year = dt.date.today().year
k = profile.key  # per-person widget key suffix, so switching profile keeps inputs separate

st.caption(
    "A calculator, not a save — nothing here is written to your data. It frames both "
    "choices as **money wasted**, netted against the asset each side ends up holding. "
    "Defaults and context come from your own data; every number is overridable."
)

target = compute.resolve_target(profile, d.targets, today_year)
default_return = round(compute.expected_return_for_target(target, d.config.expected_return_pct), 1)
return_source = ("the household expected_return_pct in config.yaml"
                 if d.config.expected_return_pct is not None
                 else "your target allocation's weighted expected return")

section("Your numbers")
house_col, loan_col, rent_col = st.columns(3)

with house_col:
    st.markdown("**The house**")
    price = st.number_input("Property price (₹)", min_value=0, value=15_000_000, step=100_000, key=f"rvb_price_{k}")
    st.caption(f"= {inr_short(price)}")
    registration_pct = st.number_input("Registration + stamp duty (% of price)", min_value=0.0, value=7.0, step=0.5, key=f"rvb_reg_{k}")
    maintenance_pct = st.number_input("Maintenance (% of price / yr)", min_value=0.0, value=0.5, step=0.1, key=f"rvb_maint_{k}")
    appreciation_pct = st.number_input("Appreciation (% p.a.)", min_value=0.0, value=5.0, step=0.5, key=f"rvb_appr_{k}")

with loan_col:
    st.markdown("**The loan**")
    down_pct = st.slider("Down payment (%)", 0, 100, 20, key=f"rvb_down_{k}")
    st.caption(f"= {inr_short(price * down_pct / 100)}")
    loan_rate_pct = st.number_input("Loan rate (% p.a.)", min_value=0.0, value=8.5, step=0.1, key=f"rvb_rate_{k}")
    tenure_years = int(st.number_input("Tenure (years)", min_value=1, value=20, step=1, key=f"rvb_tenure_{k}"))
    st.number_input("Start year (locked)", value=today_year, disabled=True, key=f"rvb_start_{k}",
                    help="Scenarios start from the current year; the charts read in calendar years.")

with rent_col:
    st.markdown("**Renting & investing**")
    rent_monthly = st.number_input("Starting rent (₹ / month)", min_value=0, value=40_000, step=1_000, key=f"rvb_rent_{k}")
    st.caption(f"= {inr_short(rent_monthly)}/mo")
    rent_inflation_pct = st.number_input("Rent inflation (% p.a.)", min_value=0.0, value=5.0, step=0.5, key=f"rvb_rentinfl_{k}")
    invest_return_pct = st.number_input(
        "Investment return (% p.a.)", min_value=0.0, value=default_return, step=0.1,
        key=f"rvb_return_{k}",
        help=f"Defaults to {return_source} ({default_return:.1f}%) — the same number "
             "behind the dashboard's Est. value today. Edit to model something else.",
    )
    horizon_years = int(st.number_input("Horizon (years)", min_value=1, value=15, step=1, key=f"rvb_horizon_{k}"))

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

# 1. Money wasted, apples to apples: each side's waste minus the asset gain
# that side holds (buyer: house appreciation; renter: investment growth).
chart_title(
    "Money wasted, net of what you own",
    help="Waste minus the asset gain each side ends up holding. Buying: registration + "
         "interest + maintenance, minus the house's appreciation. Renting: the rent, minus "
         "growth on the savings a renter invests. Below zero = the asset gained more than "
         "the waste.",
)
f = go.Figure()
f.add_trace(go.Scatter(x=yr, y=df["buy_wasted_net"], name="Buying", mode="lines+markers",
                       line=dict(color=PRIMARY, width=3)))
f.add_trace(go.Scatter(x=yr, y=df["rent_wasted_net"], name="Renting", mode="lines+markers",
                       line=dict(color=MARKER, width=3)))
f.update_layout(xaxis=dict(type="category"))
inr_axis(f, max(abs(df["buy_wasted_net"]).max(), abs(df["rent_wasted_net"]).max()))
style_fig(f, height=340)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

net_cross = None
worse = df["buy_wasted_net"] > df["rent_wasted_net"]
if worse.iloc[0] and (~worse).any():
    net_cross = int(yr.iloc[(~worse).idxmax()])
adj_caption = ("Lower line = less money truly lost. Principal repaid and a renter's invested "
               "savings were never waste; here the buyer also gets credit for appreciation and "
               "the renter for investment growth.")
if net_cross:
    adj_caption += f" Buying becomes the less wasteful choice from {net_cross}."
st.caption(adj_caption)

# 2. Headline tiles.
total_interest = monthly_emi * tenure_years * 12 - loan_principal
net_buy, net_rent = df.iloc[-1]["buy_wasted_net"], df.iloc[-1]["rent_wasted_net"]
cols = st.columns(4)
metric_tile(cols[0], "EMI / month", inr_short(monthly_emi), f"{tenure_years}-year loan", big=True)
metric_tile(cols[1], "Total interest", inr_short(total_interest), "over the full tenure", big=True)
metric_tile(cols[2], "Registration cost", inr_short(registration_cost), f"{registration_pct:.1f}% of price", big=True)
metric_tile(cols[3], "Net waste in horizon", f"Buy {inr_short(net_buy)}",
            f"Rent {inr_short(net_rent)}", color=PRIMARY, big=True,
            help="Each side's waste minus its asset gain, at the horizon — the chart's last points.")

# 3. When can you afford it? Income grows at the same rate the house
# appreciates (the user's stated assumption), EMI capped per config.
chart_title(
    f"When can you afford it? (EMI ≤ {AFFORD_EMI_CAP_PCT}% of income)",
    help=f"The affordable price is the priciest house whose EMI stays at or under "
         f"{AFFORD_EMI_CAP_PCT}% of that year's monthly income, with income growing at the "
         "same rate as the house appreciates.",
)
if monthly_income > 0:
    aff = compute.affordability_series(
        monthly_income=monthly_income, income_growth_pct=appreciation_pct, price=price,
        appreciation_pct=appreciation_pct, down_pct=down_pct, loan_rate_pct=loan_rate_pct,
        tenure_years=tenure_years, horizon_years=horizon_years, emi_cap_pct=AFFORD_EMI_CAP_PCT,
    )
    ax = (today_year + aff["year_offset"]).astype(str)
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=ax, y=aff["house_price"], name="This house", mode="lines+markers",
                            line=dict(color=SECONDARY, width=3)))
    f2.add_trace(go.Scatter(x=ax, y=aff["affordable_price"], name="You can afford", mode="lines+markers",
                            line=dict(color=PRIMARY, width=3)))
    f2.update_layout(xaxis=dict(type="category"))
    inr_axis(f2, max(aff["house_price"].max(), aff["affordable_price"].max()))
    style_fig(f2, height=320)
    st.plotly_chart(f2, width="stretch", config={"displayModeBar": False})
    affordable_now = aff.iloc[0]["affordable_price"] >= aff.iloc[0]["house_price"]
    crossing = aff[aff["affordable_price"] >= aff["house_price"]]
    if affordable_now:
        afford_caption = f"Affordable today: your EMI cap already covers this house."
    elif not crossing.empty:
        afford_caption = f"You cross into affordability in {today_year + int(crossing.iloc[0]['year_offset'])}."
    else:
        afford_caption = ("Never crosses in this horizon — with income growing at the same rate the house "
                          "appreciates, the gap stays constant; affordability only improves if raises outpace the property market.")
    st.caption(afford_caption + f" Today you can afford about {inr_short(aff.iloc[0]['affordable_price'])}.")
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

with st.expander("Net position — the fuller picture"):
    chart_title("Net position: buy vs rent",
                help="buy_net = equity built minus everything wasted; rent_net = the "
                     "renter's invested savings minus everything wasted on rent.")
    f3 = go.Figure()
    f3.add_trace(go.Scatter(x=yr, y=df["buy_net"], name="Buying (net)", mode="lines+markers",
                            line=dict(color=PRIMARY, width=3)))
    f3.add_trace(go.Scatter(x=yr, y=df["rent_net"], name="Renting (net)", mode="lines+markers",
                            line=dict(color=MARKER, width=3)))
    f3.update_layout(xaxis=dict(type="category"))
    inr_axis(f3, max(df["buy_net"].abs().max(), df["rent_net"].abs().max()))
    style_fig(f3, height=300)
    st.plotly_chart(f3, width="stretch", config={"displayModeBar": False})
    st.markdown(
        f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveat: the "
        "assumptions — appreciation, invest return, rent inflation — dominate this answer. "
        "Treat it as illustrative, not predictive.</div>",
        unsafe_allow_html=True,
    )

st.caption(
    "Approximations: yearly compounding, not monthly. No tax breaks modelled (Section "
    "24/80C, HRA). No selling or transaction costs. The affordable price assumes the "
    "down payment is available."
)
