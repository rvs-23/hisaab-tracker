import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import compute
from config import (
    CATEGORY_LABELS, HOUSE_FUND_INFLATION_PCT, HOUSE_FUND_YEARS_AHEAD, INK, LIQUID_CATEGORIES,
)
from ui import (
    accent_primary, accent_secondary, chart_title, html_table, inr_axis, inr_short,
    is_household, load_all, metric_tile, page_header, section, style_fig,
)

d = load_all()
profile = page_header("House fund", d.profiles, d.root, allow_household=True)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()
people = d.profiles if is_household(profile) else [profile]
today = dt.date.today()

liquid = ", ".join(CATEGORY_LABELS.get(c, c) for c in LIQUID_CATEGORIES)
st.caption(
    "How much you could put down on a house at the end of each year, if you keep "
    f"investing at today's pace. Counts only what you can sell: {liquid}. EPF, PPF, NPS, "
    "AIF and the emergency fund stay out. Nothing here is saved; play with the inputs."
)

default_rate = d.config.expected_return_pct or 10.0
default_pace = compute.liquid_pace(people, d.contributions, today)
default_growth = sum(p.forward_increment_pct for p in people) / len(people)

section("Assumptions")
c = st.columns(3)
monthly = c[0].number_input("Invest per month (₹)", 0, None, int(round(default_pace / 12, -3)),
                            5_000, key="hf_monthly",
                            help=f"Default: liquid investments recorded for {today.year} so far, "
                                 "scaled up to a full year, divided by 12. If Investments are "
                                 "behind, this reads low, so set your real number.")
c[0].caption(f"= {inr_short(monthly)} a month, {inr_short(12 * monthly)} a year")
growth = c[1].number_input("Monthly amount grows (% a year)", 0.0, 50.0, float(default_growth), 1.0,
                           key="hf_growth",
                           help="How much more you invest each year as income rises. "
                                "Default: forward_increment_pct from the profile(s).")
rate = c[2].number_input("Return (% a year)", 0.0, 30.0, float(default_rate), 0.5, key="hf_rate",
                         help="Growth on everything already invested and every new rupee.")
c = st.columns(3)
inflation = c[0].number_input("Inflation (% a year)", 0.0, 20.0, HOUSE_FUND_INFLATION_PCT, 0.5,
                              key="hf_inflation",
                              help="Turns each future figure into today's money: what it would "
                                   "buy at today's prices.")
years = c[1].slider("Years ahead", 1, 20, HOUSE_FUND_YEARS_AHEAD, key="hf_years")
with c[2]:
    st.write("")
    include_opening = st.checkbox("Count opening corpus", value=True, key="hf_opening",
                                  help="Money invested before tracking began. Its mix isn't "
                                       "recorded, so it's assumed sellable.")

corpus = compute.liquid_corpus_today(people, d.income, d.contributions, d.adjustments,
                                     today.year, rate, include_opening)
fund = compute.house_fund(corpus, 12 * monthly, growth, rate, years, today, inflation)

section("At a glance")
t = st.columns(3)
metric_tile(t[0], "Liquid corpus today", inr_short(corpus), "already invested, grown", big=True,
            help=f"Liquid contributions grown at {rate:g}% to {today.year}"
                 + (", plus the opening corpus." if include_opening else "."))
mid = fund.iloc[min(5, years)]
metric_tile(t[1], f"By Dec {int(mid['year'])}", inr_short(mid["available"]),
            f"{inr_short(mid['todays_money'])} in today's money<br>"
            f"{inr_short(mid['new_savings'])} of it new savings", color=PRIMARY, big=True)
last = fund.iloc[-1]
metric_tile(t[2], f"By Dec {int(last['year'])}", inr_short(last["available"]),
            f"{inr_short(last['todays_money'])} in today's money<br>"
            f"{inr_short(last['new_savings'])} of it new savings", color=SECONDARY, big=True)

chart_title("Down payment available, by year",
            help="Each bar is the whole pot at the end of that year: today's corpus grown, "
                 "plus everything saved from now on, grown.")
xs = fund["year"].astype(int).astype(str)
f = go.Figure()
f.add_bar(x=xs, y=fund["from_today"], name="Already invested", marker_color=SECONDARY)
f.add_bar(x=xs, y=fund["new_savings"], name="New savings", marker_color=PRIMARY,
          text=[inr_short(v) for v in fund["available"]], textposition="outside")
f.add_scatter(x=xs, y=fund["todays_money"], name=f"In today's money ({inflation:g}% inflation)",
              mode="lines+markers", line=dict(color=INK, width=2, dash="dash"), marker=dict(size=5))
f.update_traces(cliponaxis=False)
f.update_layout(barmode="stack", xaxis=dict(type="category"))
inr_axis(f, fund["available"].max())
style_fig(f, height=360)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

html_table(
    fund,
    {"year": "Buy at end of", "available": "Down payment", "todays_money": "In today's money",
     "from_today": "Already invested", "new_savings": "New savings"},
    formats={"year": lambda v: f"{int(v)}", "available": inr_short, "todays_money": inr_short,
             "from_today": inr_short, "new_savings": inr_short},
)
st.caption("Yearly compounding, with each year's savings landing at year end. Registration "
           "and stamp duty aren't subtracted; keep them aside from this number.")
