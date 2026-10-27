import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import compute
from config import (
    CATEGORY_LABELS, HOUSE_FUND_EXCLUDED, HOUSE_FUND_GROWTH_PCT, HOUSE_FUND_INFLATION_PCT,
    HOUSE_FUND_YEARS, INK,
)
from ui import (
    accent_primary, accent_secondary, chart_title, edit_card, html_table, inr_axis, inr_short,
    is_household, load_all, metric_tile, page_header, section, style_fig,
)

d = load_all()
profile = page_header("House fund", d.profiles, d.root, allow_household=True)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()
people = d.profiles if is_household(profile) else [profile]
today = dt.date.today()
first_year, last_year = HOUSE_FUND_YEARS

left_out = ", ".join(CATEGORY_LABELS.get(c, c) for c in HOUSE_FUND_EXCLUDED)
corpus_help = (f"Everything invested except {left_out}: retirement money that can't go "
               "toward a house. Includes the opening corpus. Grown at the return below; a "
               "projection from what was put in, not a market value.")
st.caption(
    "If we keep investing at this pace, what will our corpus be at the end of each year? "
    f"{first_year}–{today.year - 1} are what we actually built; {today.year} on is the projection. "
    "Nothing here is saved; change the inputs and everything redraws."
)

default_monthly = compute.monthly_pace(people, d.contributions, today, HOUSE_FUND_EXCLUDED)
default_rate = d.config.expected_return_pct or 10.0

section("Assumptions")
c = st.columns(4)
monthly = c[0].number_input("Combined monthly investment (₹)", 0, None,
                            int(round(default_monthly, -3)), 5_000, key="hf_monthly",
                            help=f"Default: what's recorded for {today.year} so far (excluding "
                                 f"{left_out}), scaled to a full year, divided by 12. If "
                                 "Investments are behind, this reads low.")
c[0].caption(f"= {inr_short(monthly)} a month")
growth = c[1].number_input("It grows (% a year)", 0.0, 50.0, HOUSE_FUND_GROWTH_PCT, 1.0,
                           key="hf_growth", help="How much more you invest each year as income rises.")
rate = c[2].number_input("Return (% a year)", 0.0, 30.0, float(default_rate), 0.5, key="hf_rate",
                         help="Growth on everything invested.")
inflation = c[3].number_input("Inflation (% a year)", 0.0, 20.0, HOUSE_FUND_INFLATION_PCT, 0.5,
                              key="hf_inflation",
                              help="Taken off to show each year in today's money: what it would "
                                   "buy at today's prices.")

fund = compute.corpus_by_year(people, d.income, d.contributions, d.adjustments, first_year,
                              last_year, monthly, growth, rate, inflation, today, HOUSE_FUND_EXCLUDED)
now = fund[fund["year"] == today.year].iloc[0]
mid = fund[fund["year"] == min(today.year + 5, last_year)].iloc[0]
end = fund.iloc[-1]

section("At a glance")
t = st.columns(3)
metric_tile(t[0], f"Corpus by Dec {today.year}", inr_short(now["total"]),
            f"{inr_short(now['invested_by_now'])} invested and grown so far", big=True,
            help=corpus_help)
for col, row, color in ((t[1], mid, PRIMARY), (t[2], end, SECONDARY)):
    metric_tile(col, f"By Dec {int(row['year'])}", inr_short(row["total"]),
                f"{inr_short(row['todays_money'])} in today's money", color=color, big=True,
                help=corpus_help)

chart_title(f"Total corpus at the end of each year, {first_year}–{last_year}", help=corpus_help)
xs = fund["year"].astype(int).astype(str)
f = go.Figure()
f.add_bar(x=xs, y=fund["invested_by_now"], name=f"Built by {today.year}, grown", marker_color=SECONDARY)
f.add_bar(x=xs, y=fund["new_savings"], name="New savings, grown", marker_color=PRIMARY,
          text=[inr_short(v) for v in fund["total"]], textposition="outside")
f.add_scatter(x=xs, y=fund["todays_money"], name=f"In today's money ({inflation:g}% inflation)",
              mode="lines+markers", line=dict(color=INK, width=2, dash="dash"), marker=dict(size=5))
f.update_traces(cliponaxis=False)
f.update_layout(barmode="stack", xaxis=dict(type="category"))
inr_axis(f, fund["total"].max())
style_fig(f, height=380)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

html_table(
    fund,
    {"year": "End of", "total": "Corpus", "todays_money": "In today's money",
     "invested_by_now": f"Built by {today.year}", "new_savings": "New savings"},
    formats={"year": lambda v: f"{int(v)}", "total": inr_short, "todays_money": inr_short,
             "invested_by_now": inr_short, "new_savings": inr_short},
    row_class=lambda r: "proj" if r["is_projected"] else ("cur" if r["year"] == today.year else ""),
)
st.caption("Yearly compounding, each year's savings landing at year end.")

section("Plan a down payment")
with edit_card("How much do we need to invest for it?"):
    r = st.columns(2)
    target_cr = r[0].number_input("Down payment (₹ Cr, today's prices)", 0.0, 50.0, 1.0, 0.1,
                                  key="hf_target",
                                  help="In today's prices. It's grown by the inflation above to the "
                                       "buying year, since house prices rise too.")
    years_out = r[1].number_input("In how many years", 1, 30, 5, 1, key="hf_years_out")
    buy_year = today.year + int(years_out)
    target = target_cr * 1e7 * (1 + inflation / 100) ** years_out
    corpus_now = compute.corpus_at(people, d.income, d.contributions, d.adjustments, today.year,
                                   rate, HOUSE_FUND_EXCLUDED)
    need = compute.monthly_needed(corpus_now, target, buy_year, growth, rate, today)
    at_pace = compute.house_fund(corpus_now, 12 * monthly, growth, rate, int(years_out),
                                 today).iloc[-1]["available"]
    gap = target - at_pace

    o = st.columns(3)
    metric_tile(o[0], f"Needed by Dec {buy_year}", inr_short(target),
                f"₹{target_cr:g} Cr today, plus {inflation:g}% a year", big=True)
    metric_tile(o[1], "Invest per month", inr_short(need),
                f"you're at {inr_short(monthly)}; "
                + (f"{inr_short(need - monthly)} more" if need > monthly else "you're ahead"),
                color=PRIMARY, big=True,
                help=f"Starting now, growing {growth:g}% a year, at a {rate:g}% return.")
    metric_tile(o[2], "At your current pace", inr_short(at_pace),
                f"{inr_short(gap)} short" if gap > 0 else f"{inr_short(-gap)} to spare",
                color=SECONDARY, big=True, help=corpus_help)
