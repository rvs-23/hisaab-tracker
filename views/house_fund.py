import datetime as dt

import plotly.graph_objects as go
import streamlit as st

import compute
from config import CATEGORY_LABELS, HOUSE_FUND_YEARS_AHEAD, LIQUID_CATEGORIES
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
    f"investing at today's pace. Counts only what you can sell: {liquid}. EPF / PPF / "
    "NPS and the emergency fund stay out. Nothing here is saved; play with the inputs."
)

default_rate = d.config.expected_return_pct or 10.0
default_pace = compute.liquid_pace(people, d.contributions, today)
default_growth = sum(p.forward_increment_pct for p in people) / len(people)

section("Assumptions")
c = st.columns(5)
rate = c[0].number_input("Return (% a year)", 0.0, 30.0, float(default_rate), 0.5, key="hf_rate",
                         help="Growth on everything already invested and every new rupee.")
pace = c[1].number_input("Invest per year (₹)", 0, None, int(round(default_pace, -3)), 10_000,
                         key="hf_pace",
                         help=f"Default: liquid investments recorded for {today.year} so far, "
                              "scaled up to a full year. If Actuals are behind, this reads low, "
                              "so set your real number.")
c[1].caption(f"= {inr_short(pace)} a year")
growth = c[2].number_input("Pace grows (% a year)", 0.0, 50.0, float(default_growth), 1.0,
                           key="hf_growth",
                           help="How much more you invest each year as income rises. "
                                "Default: forward_increment_pct from the profile(s).")
years = c[3].slider("Years ahead", 1, 20, HOUSE_FUND_YEARS_AHEAD, key="hf_years")
with c[4]:
    st.write("")
    include_opening = st.checkbox("Count opening corpus", value=True, key="hf_opening",
                                  help="Money invested before tracking began. Its mix isn't "
                                       "recorded, so it's assumed sellable.")

corpus = compute.liquid_corpus_today(people, d.income, d.contributions, d.adjustments,
                                     today.year, rate, include_opening)
fund = compute.house_fund(corpus, pace, growth, rate, years, today)

section("At a glance")
t = st.columns(3)
metric_tile(t[0], "Liquid corpus today", inr_short(corpus), "already invested, grown", big=True,
            help=f"Liquid contributions grown at {rate:g}% to {today.year}"
                 + (", plus the opening corpus." if include_opening else "."))
mid = fund.iloc[min(5, years)]
metric_tile(t[1], f"By Dec {int(mid['year'])}", inr_short(mid["available"]),
            f"{inr_short(mid['new_savings'])} of it new savings", color=PRIMARY, big=True)
last = fund.iloc[-1]
metric_tile(t[2], f"By Dec {int(last['year'])}", inr_short(last["available"]),
            f"{inr_short(last['new_savings'])} of it new savings", color=SECONDARY, big=True)

chart_title("Down payment available, by year",
            help="Each bar is the whole pot at the end of that year: today's corpus grown, "
                 "plus everything saved from now on, grown.")
xs = fund["year"].astype(int).astype(str)
f = go.Figure()
f.add_bar(x=xs, y=fund["from_today"], name="Already invested", marker_color=SECONDARY)
f.add_bar(x=xs, y=fund["new_savings"], name="New savings", marker_color=PRIMARY,
          text=[inr_short(v) for v in fund["available"]], textposition="outside")
f.update_traces(cliponaxis=False)
f.update_layout(barmode="stack", xaxis=dict(type="category"))
inr_axis(f, fund["available"].max())
style_fig(f, height=360)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

html_table(
    fund,
    {"year": "Buy at end of", "available": "Down payment", "from_today": "Already invested",
     "new_savings": "New savings"},
    formats={"year": lambda v: f"{int(v)}", "available": inr_short,
             "from_today": inr_short, "new_savings": inr_short},
)
st.caption("Yearly compounding, with each year's savings landing at year end. Registration "
           "and stamp duty aren't subtracted; keep them aside from this number.")
