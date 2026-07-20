"""Rent vs buy: a stateless calculator, not a save.

Frames the decision the way the household actually thinks about it — money
*wasted*, not net worth. Buying wastes registration/stamp duty, loan
interest, and maintenance; renting wastes the rent itself. Nothing on this
page reads or writes contributions.csv/income.csv/etc — it's pure what-if.
"""

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import compute
from ui import (
    FS_BODY, MARKER, accent_primary, chart_title, inr_axis, inr_short,
    load_all, metric_tile, page_header, section, style_fig,
)

d = load_all()
profile = page_header("Rent vs buy", d.profiles)
PRIMARY = accent_primary()
today_year = dt.date.today().year
k = profile.key  # per-person widget key suffix, so switching profile keeps inputs separate

st.caption(
    "A calculator, not a save — nothing here is written to your data. It frames both "
    "choices as **money wasted**: spending that buys you nothing lasting, rather than "
    "net worth. Defaults and context come from your own data; every number is overridable."
)

target = compute.resolve_target(profile, d.targets, today_year)
default_return = round(compute.expected_return_for_target(target, d.config.expected_return_pct), 1)
return_source = ("the household expected_return_pct in config.yaml"
                 if d.config.expected_return_pct is not None
                 else "your target allocation's weighted expected return")

section("Your numbers")
c0, c1, c2, c3 = st.columns(4)
# Locked: the scenario starts now — every projection reads in calendar years.
c0.number_input("Start year (locked)", value=today_year, disabled=True, key=f"rvb_start_{k}",
                help="Scenarios start from the current year; the charts below read in calendar years.")
price = c1.number_input("Property price (₹)", min_value=0, value=15_000_000, step=100_000, key=f"rvb_price_{k}")
c1.caption(f"= {inr_short(price)}")
down_pct = c2.slider("Down payment (%)", 0, 100, 20, key=f"rvb_down_{k}")
c2.caption(f"= {inr_short(price * down_pct / 100)}")
loan_rate_pct = c3.number_input("Home-loan rate (% p.a.)", min_value=0.0, value=8.5, step=0.1, key=f"rvb_rate_{k}")

c4, c5, c6, c7 = st.columns(4)
tenure_years = int(c4.number_input("Loan tenure (years)", min_value=1, value=20, step=1, key=f"rvb_tenure_{k}"))

registration_pct = c5.number_input("Registration + stamp duty (% of price)", min_value=0.0, value=7.0, step=0.5, key=f"rvb_reg_{k}")
maintenance_pct = c6.number_input("Maintenance (% of price / yr)", min_value=0.0, value=0.5, step=0.1, key=f"rvb_maint_{k}")
appreciation_pct = c7.number_input("Property appreciation (% p.a.)", min_value=0.0, value=5.0, step=0.5, key=f"rvb_appr_{k}")
c8, c9, c10, c11 = st.columns(4)
horizon_years = int(c8.number_input("Horizon (years)", min_value=1, value=15, step=1, key=f"rvb_horizon_{k}"))
rent_monthly = c9.number_input("Starting rent (₹ / month)", min_value=0, value=40_000, step=1_000, key=f"rvb_rent_{k}")
c9.caption(f"= {inr_short(rent_monthly)}/mo")
rent_inflation_pct = c10.number_input("Rent inflation (% p.a.)", min_value=0.0, value=5.0, step=0.5, key=f"rvb_rentinfl_{k}")
invest_return_pct = c11.number_input(
    "Expected investment return (% p.a.)", min_value=0.0, value=default_return, step=0.1,
    key=f"rvb_return_{k}",
    help=f"Defaults to {return_source} ({default_return:.1f}%) — edit to model something else.",
)
st.caption(
    f"Investment return defaults to {default_return:.1f}% — {return_source}, the same "
    "number behind the dashboard's Est. value today."
)

# Derived once, up front, so both "For you" and the tile row below reuse the
# same numbers as the calculator itself (no separate recompute path).
down_payment = price * down_pct / 100
loan_principal = price - down_payment
registration_cost = price * registration_pct / 100
monthly_emi = compute.emi(loan_principal, loan_rate_pct, tenure_years)
maintenance_annual = price * maintenance_pct / 100

# "For you": how these numbers stack up against the person's own real data —
# read-only context (via load_all), not an input. Recomputes live as the
# calculator's inputs change above; kept to muted captions so it stays
# subordinate to the money-wasted chart below, not competing with it.
bs = compute.budget_series(profile, d.income)
entered = bs[~bs["is_projected"]]
monthly_income = float(entered.iloc[-1]["total_income"]) / 12 if not entered.empty else 0.0
cur_row = bs[bs["year"] == today_year]
monthly_goal = float(cur_row.iloc[0]["monthly_investment"]) if not cur_row.empty else 0.0
opening = compute.opening_corpus(d.adjustments, profile.key)
ef_held = compute.emergency_fund_actual(d.adjustments, profile.key) or None
_, nw_potential = compute.net_worth_to_date(
    profile, d.income, d.contributions, d.targets, today_year, opening=opening, emergency_fund=ef_held
)

context_lines = []
if monthly_income > 0:
    emi_pct = 100 * monthly_emi / monthly_income
    line = f"EMI is **{emi_pct:.0f}%** of your monthly income."
    if emi_pct > 40:
        line += " That's a heavy monthly commitment — many guidelines suggest staying under 40%."
    context_lines.append(line)
if nw_potential > 0:
    upfront_cost = down_payment + registration_cost
    upfront_pct = 100 * upfront_cost / nw_potential
    context_lines.append(
        f"Upfront cost (down payment + registration) is {inr_short(upfront_cost)}, about "
        f"**{upfront_pct:.0f}%** of your estimated net worth today."
    )
if monthly_goal > 0:
    monthly_buy_cost = monthly_emi + maintenance_annual / 12
    goal_pct = 100 * monthly_buy_cost / monthly_goal
    context_lines.append(
        f"Buying at these numbers would consume **{goal_pct:.0f}%** of your planned "
        f"monthly investment goal."
    )
if context_lines:
    section("For you")
    for line in context_lines:
        st.caption(line)

df = compute.rent_vs_buy(
    price=price, down_pct=down_pct, loan_rate_pct=loan_rate_pct, tenure_years=tenure_years,
    registration_pct=registration_pct, maintenance_pct=maintenance_pct,
    appreciation_pct=appreciation_pct, rent_monthly=rent_monthly,
    rent_inflation_pct=rent_inflation_pct, invest_return_pct=invest_return_pct,
    horizon_years=horizon_years,
)

# 1. Money wasted, cumulative — the philosophy leads.
chart_title(
    "Money wasted, cumulative",
    help="Waste = money that buys you nothing lasting. Buying wastes registration + loan "
         "interest + maintenance; renting wastes the rent itself.",
)
yr = (today_year - 1 + df["year"]).astype(str)  # calendar years from the locked start
f = go.Figure()
f.add_trace(go.Scatter(x=yr, y=df["buy_wasted_cum"], name="Buying", mode="lines+markers",
                       line=dict(color=PRIMARY, width=3)))
f.add_trace(go.Scatter(x=yr, y=df["rent_wasted_cum"], name="Renting", mode="lines+markers",
                       line=dict(color=MARKER, width=3)))
f.update_layout(xaxis=dict(type="category"))
inr_axis(f, max(df["buy_wasted_cum"].max(), df["rent_wasted_cum"].max()))
style_fig(f, height=340)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

crossover = compute.rent_vs_buy_crossover_year(df)
waste_caption = (
    "Waste = registration + stamp duty + loan interest + maintenance (buying) vs the rent "
    "itself (renting) — never the principal you repay or a renter's invested savings."
)
if crossover is not None:
    waste_caption += f" Buying overtakes renting as the less-wasteful choice from year {crossover}."
st.caption(waste_caption)

# 2. Tile row: the headline figures.
total_interest = monthly_emi * tenure_years * 12 - loan_principal
wasted_buy, wasted_rent = df.iloc[-1]["buy_wasted_cum"], df.iloc[-1]["rent_wasted_cum"]

cols = st.columns(4)
metric_tile(cols[0], "EMI / month", inr_short(monthly_emi), f"{tenure_years}-year loan", big=True)
metric_tile(cols[1], "Total interest", inr_short(total_interest), "over the full tenure", big=True)
metric_tile(cols[2], "Registration cost", inr_short(registration_cost), f"{registration_pct:.1f}% of price", big=True)
metric_tile(cols[3], "Wasted in horizon", f"Buy {inr_short(wasted_buy)}", f"Rent {inr_short(wasted_rent)}",
           color=PRIMARY, big=True)

# 3. Net position — the fuller (and shakier) picture.
with st.expander("Net position — the fuller picture"):
    chart_title("Net position: buy vs rent",
               help="buy_net = equity built minus everything wasted; rent_net = the "
                    "renter's invested savings minus everything wasted on rent.")
    f2 = go.Figure()
    f2.add_trace(go.Scatter(x=yr, y=df["buy_net"], name="Buying (net)", mode="lines+markers",
                           line=dict(color=PRIMARY, width=3)))
    f2.add_trace(go.Scatter(x=yr, y=df["rent_net"], name="Renting (net)", mode="lines+markers",
                           line=dict(color=MARKER, width=3)))
    f2.update_layout(xaxis=dict(type="category"))
    inr_axis(f2, max(df["buy_net"].abs().max(), df["rent_net"].abs().max()))
    style_fig(f2, height=300)
    st.plotly_chart(f2, width="stretch", config={"displayModeBar": False})
    st.markdown(
        f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveat: this nets "
        "built value against waste, but the assumptions — appreciation, invest return, "
        "rent inflation — dominate this answer far more than the waste view above. "
        "Treat it as illustrative, not predictive.</div>",
        unsafe_allow_html=True,
    )

st.caption(
    "Approximations: yearly compounding, not monthly (contributions and interest are "
    "aggregated to one lump per year). No tax breaks modelled (Section 24/80C, HRA). No "
    "selling or transaction costs on either side."
)
