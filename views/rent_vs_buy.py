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
from config import EMI_SHARE_OF_WANTS_INVESTMENT_PCT, RENTER_INVEST_DISCIPLINE_PCT
from ui import (
    CHART_TEXT, COST_LINE, FS_BODY, MARKER, accent_primary, accent_secondary,
    chart_title, inr_axis, inr_short, load_all, metric_tile, page_header, style_fig,
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

sc1, sc2, sc3, _ = st.columns([1, 1, 1, 1])
sc1.number_input("Start year (locked)", value=today_year, disabled=True, key=f"rvb_start_{k}",
                 help="Scenarios start from the current year; the chart reads in calendar years.")
horizon_years = int(sc2.number_input("Horizon (years)", min_value=1, value=15, step=1, key=f"rvb_horizon_{k}"))
inflation_pct = sc3.number_input(
    "Inflation (% p.a.)", min_value=0.0, value=6.0, step=0.5, key=f"rvb_infl_{k}",
    help="Used two ways in When to buy: maintenance rises with it, and every future "
         "rupee is discounted back to today's money — otherwise a cost in 2060 counts "
         "the same as one today. Rent and property have their own rates above. "
         "Set 0 to work in nominal rupees.",
)

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
# Gridlines start at 1Cr cumulative / 25L per year and coarsen from there — a
# fixed step would draw thirty lines once the house is a 15Cr scenario.
top = max(s.max() for s in series.values()) * 1.08
inr_axis(f, top, min_step=25_00_000 if per_year else 1_00_00_000)
style_fig(f, height=560)
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
discipline_note = (f"assuming the renter invests {invest_discipline_pct:.0f}% of the monthly "
                   f"difference (a buyer's EMI is forced saving; a renter tends to spend some)"
                   if invest_discipline_pct < 100 else
                   "assuming the renter invests every spare rupee")
st.caption(
    f"By {horizon_year}, **{leaner.lower()} wastes {inr_short(abs(gap))} less**: buying burns "
    f"{inr_short(buy_end)} (registration + interest + maintenance) against {inr_short(rent_end)} "
    f"of rent. Letting the rest sit idle instead of investing it pushes renting's waste to "
    f"{inr_short(idle_end)} — the {inr_short(idle_end - rent_end)} gap is what the investing is "
    f"worth, {discipline_note}."
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

opening = compute.opening_corpus(d.adjustments, profile.key)
ef_held = compute.emergency_fund_actual(d.adjustments, profile.key) or None
_, nw_potential = compute.net_worth_to_date(
    profile, d.income, d.contributions, d.targets, today_year, opening=opening,
    emergency_fund=ef_held, flat_return=d.config.expected_return_pct,
)
# net_worth_to_date folds in the emergency fund — the recorded one, or the
# derived target when nothing is recorded. Subtract whichever it actually used,
# or the reserve silently becomes down-payment money.
ef_reserved = ef_held if ef_held is not None else compute.emergency_fund_target(
    profile, d.income, today_year)
investable = max(0.0, nw_potential - ef_reserved)

# Affordability, from the budget rather than gross income. The envelope is
# wants + investment: needs are already committed (an EMI can't come out of
# groceries), so what a house can actually claim is discretionary spending plus
# the money that would otherwise be invested. The share is yours to set.
chart_title(
    "What you can afford",
    help="Your budget's wants + investment for the current year, not gross income. "
         "Needs are committed spending and stay out of it; a house is funded by "
         "giving up discretionary spend and investing less. The share below is how "
         "much of that envelope a home loan may claim.",
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
    envelope = monthly_wants + monthly_investment

    share_pct = st.slider(
        "Share of wants + investment an EMI may take (%)", 10, 100,
        EMI_SHARE_OF_WANTS_INVESTMENT_PCT, step=5, key=f"rvb_emishare_{k}",
    )
    emi_budget = envelope * share_pct / 100
    max_loan = compute.max_loan_for_emi(emi_budget, loan_rate_pct, tenure_years)

    acols = st.columns(3)
    metric_tile(acols[0], "Wants + investment / month", inr_short(envelope),
                f"{inr_short(monthly_wants)} wants + {inr_short(monthly_investment)} invested", big=True)
    metric_tile(acols[1], "EMI you can carry", inr_short(emi_budget),
                f"{share_pct}% of that envelope", color=SECONDARY, big=True)
    metric_tile(acols[2], "Loan it supports", inr_short(max_loan),
                f"{loan_rate_pct:.1f}% over {tenure_years} years", color=PRIMARY, big=True)
    st.caption(
        f"At {share_pct}% of your {inr_short(envelope)} wants + investment, you can carry a "
        f"{inr_short(emi_budget)} EMI — a {inr_short(max_loan)} loan over {tenure_years} years. "
        "That's the borrowing alone; a house also needs your down payment on top (see When to buy)."
    )
else:
    st.caption("Add this year's income to see what your budget can carry.")
    monthly_investment = 0.0
    emi_budget = 0.0  # no budget known: the timing model skips the EMI test

# When to buy. Renting isn't forever — every year of waiting is a real choice,
# so price them all on the same terms and let the minimum speak.
chart_title(
    "When to buy",
    help="Total waste over the whole ownership — rent while you wait, plus "
         "registration, all the loan's interest, and maintenance once you own. "
         "Waiting costs rent and a pricier house, but your corpus compounds into a "
         "bigger down payment and a smaller loan. Every option carries its full "
         "loan, so waiting can't look free. Assumes ready-to-move-in: rent stops "
         "the day you buy.",
)
# Starting corpus: defaults to the dashboard's estimated value less the
# emergency fund, but it's an estimate built on assumed returns — so it can be
# overridden, or excluded entirely to see the timing on new savings alone.
cc1, cc2, _ = st.columns([1, 1, 2])
use_corpus = cc1.checkbox(
    "Use my current savings", value=True, key=f"rvb_usecorpus_{k}",
    help="On: start from what you've already invested. Off: start from zero and "
         "let only your monthly investing build the down payment.",
)
corpus_input = cc2.number_input(
    "Starting corpus (₹)", min_value=0, value=int(round(investable)), step=100_000,
    disabled=not use_corpus, key=f"rvb_corpus_{k}",
    help="Defaults to your estimated portfolio value today minus the emergency "
         "fund — the same figure the dashboard shows. Override it for a what-if.",
)
starting_corpus = float(corpus_input) if use_corpus else 0.0
cc2.caption(f"= {inr_short(starting_corpus)}")
if use_corpus and abs(corpus_input - investable) > 1:
    cc1.caption(f"Your data says {inr_short(investable)}.")

deploy_pct = st.slider(
    "Share of savings you'd put into the house (%)", 10, 100, 60, step=5,
    key=f"rvb_deploy_{k}",
    help="How much of your corpus you'd actually spend on the down payment + "
         "registration — the rest stays invested. Draining all of it minimises "
         "the loan but leaves you illiquid, so the realistic answer is below 100%, "
         "which pushes the cheapest year later.",
)

timing = compute.best_buy_year(
    price=price, down_pct=down_pct, loan_rate_pct=loan_rate_pct, tenure_years=tenure_years,
    registration_pct=registration_pct, maintenance_pct=maintenance_pct,
    appreciation_pct=appreciation_pct, rent_monthly=rent_monthly,
    rent_inflation_pct=rent_inflation_pct, invest_return_pct=invest_return_pct,
    horizon_years=horizon_years, starting_corpus=starting_corpus,
    monthly_saving=monthly_investment, inflation_pct=inflation_pct,
    emi_budget=emi_budget, corpus_deploy_pct=deploy_pct,
)
feasible = timing[timing["feasible"]]
buy_years = (today_year + timing["wait_years"]).astype(str)

f2 = go.Figure()
f2.add_trace(go.Bar(
    x=buy_years, y=timing["total_wasted"], showlegend=False,
    marker_color=[PRIMARY if row.feasible else COST_LINE for row in timing.itertuples()],
    hovertemplate="Buy in %{x}: ₹%{y:,.0f} wasted<extra></extra>",
))
# The colour carries the affordability split, so it needs a key on the chart —
# empty traces exist only to put those two swatches in the legend.
for name, colour, shown in [("You can afford this year", PRIMARY, True),
                            ("Corpus can't fund it yet", COST_LINE,
                             not bool(timing["feasible"].all()))]:
    if shown:
        f2.add_trace(go.Bar(x=[None], y=[None], name=name, marker_color=colour))
if not feasible.empty:
    best = timing.loc[feasible["total_wasted"].idxmin()]
    # "Cheapest" alone misleads when the early bars are unaffordable: the pick is
    # only the best of the years you can actually transact in.
    pick = "cheapest you can afford" if not timing["feasible"].all() else "cheapest"
    # Point the label inward when the winner sits near the right edge, or the
    # text runs off the canvas.
    late = int(best["wait_years"]) > len(timing) * 0.6
    f2.add_annotation(x=str(today_year + int(best["wait_years"])), y=float(best["total_wasted"]),
                      text=f"{pick}: {inr_short(best['total_wasted'])} wasted",
                      showarrow=True, arrowhead=0, ay=-34, ax=-60 if late else 0,
                      xanchor="right" if late else "center",
                      font=dict(color=PRIMARY, size=12))
inr_axis(f2, timing["total_wasted"].max() * 1.15, min_step=1_00_00_000)
style_fig(f2, height=380)
# Both axes carry a title here: bare rupee bars over bare years don't say what
# is being measured, and "lower is better" is the opposite of the usual reading.
f2.update_layout(margin=dict(l=8, r=8, t=34, b=8), barmode="overlay",
                 legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
f2.update_yaxes(title_text="Total wasted over the whole loan — lower is better",
                title_font=dict(size=12, color=CHART_TEXT))
f2.update_xaxes(title_text="Year you buy", title_font=dict(size=12, color=CHART_TEXT))
st.plotly_chart(f2, width="stretch", config={"displayModeBar": False})

if feasible.empty:
    blocker = ("the EMI never fits your budget" if timing["cash_ok"].any()
               else "your corpus never covers registration plus the minimum down payment")
    st.caption(
        f"No year in this horizon works — {blocker}. Stretch the horizon, lower the "
        "price, or raise the share of wants + investment an EMI may take."
    )
elif starting_corpus <= 0 and monthly_investment <= 0:
    st.caption("Record your savings on Actuals, or set a starting corpus above, to price the waiting years.")
else:
    # Compare like with like: the baseline is the earliest year you could
    # actually buy, not year 0. When the corpus can't fund today's purchase,
    # "cheaper than buying today" is a comparison against something you can't do.
    baseline = timing[timing["feasible"]].iloc[0]
    baseline_year = today_year + int(baseline["wait_years"])
    best_year = today_year + int(best["wait_years"])
    gap = float(baseline["total_wasted"] - best["total_wasted"])

    if not bool(timing.iloc[0]["feasible"]):
        st.caption(
            f"**You can't buy this house yet** — {inr_short(starting_corpus)} invested doesn't "
            f"cover {inr_short(registration_cost)} registration plus the "
            f"{inr_short(down_payment)} minimum down payment. {baseline_year} is the first "
            f"year your corpus gets there."
        )

    if best_year == baseline_year:
        st.caption(
            f"**Buy as soon as you can — {best_year}.** Every year you wait after that "
            f"adds more in rent and appreciation than your corpus gains: waiting one "
            f"more year wastes {inr_short(float(timing.iloc[int(best['wait_years']) + 1]['total_wasted'] - best['total_wasted']))} extra."
            if int(best["wait_years"]) + 1 < len(timing) else
            f"**Buy as soon as you can — {best_year}.**"
        )
    else:
        loan_verb = "falls to" if best["loan"] < baseline["loan"] else "rises to"
        st.caption(
            f"**{best_year} wastes the least — {inr_short(best['total_wasted'])}**, "
            f"{inr_short(gap)} less than buying in {baseline_year} "
            f"({inr_short(baseline['total_wasted'])}). By {best_year} the house costs "
            f"{inr_short(best['price_then'])} and your corpus is {inr_short(best['corpus'])}, "
            f"so the loan {loan_verb} {inr_short(best['loan'])} — the interest saved is what "
            f"pays for the {inr_short(best['rent_paid'])} of rent in the meantime."
        )
    st.caption(
        "Each bar is one decision priced end to end: rent until you buy, then "
        "registration, every rupee of the loan's interest, and maintenance for the "
        "whole tenure"
        + (f", all discounted to today's rupees at {inflation_pct:.1f}% inflation. "
           if inflation_pct else ", in nominal rupees. ")
        + ("Greyed bars fail one of the two affordability tests: enough cash for "
           "registration plus the down payment, and an EMI inside your budget."
           if not timing["feasible"].all() else "")
    )

st.markdown(
    f"<div style='color:var(--muted);font-size:{FS_BODY}'>Honest caveats. "
    "<b>Waste, not wealth</b> — the buyer ends up owning a house and the renter a "
    "portfolio; neither asset is counted here, so a low bar is not the same as being "
    "better off. <b>When to buy deploys the share of your corpus you set above</b> into "
    "the house; the rest stays invested. A bigger share shrinks the loan but leaves you "
    "less liquid. "
    "<b>Affordability is deliberately conservative</b>: rent lives in your needs bucket, "
    "so buying frees up money the envelope doesn't credit you with. "
    "<b>Ready-to-move-in</b> — rent stops the day you buy, no construction gap or "
    "pre-EMI. Interest follows a real monthly amortization; maintenance, rent and "
    "returns compound yearly. No tax breaks modelled (Section 24/80C, HRA), no selling "
    "or brokerage costs, and the verdict is only as good as the appreciation and return "
    "you assume.</div>",
    unsafe_allow_html=True,
)
