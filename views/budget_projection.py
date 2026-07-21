import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from config import (
    DEFAULT_BASE_SPLIT, DEFAULT_INCREMENT_SPLIT, PROFILE_BASE_SPLITS,
    PROFILE_INCREMENT_SPLITS,
)
from ui import (
    FS_BODY, NEEDS, SAND, accent_primary, accent_secondary, chart_title,
    html_table, inr_short, load_all, metric_tile, page_header, pretty_category,
    resync, section, seed_slice_sig, slice_sig, stale_since_open, style_fig,
)

CURRENT_YEAR = dt.date.today().year

d = load_all()
active = page_header("Budget", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
base_split = PROFILE_BASE_SPLITS.get(active.key, DEFAULT_BASE_SPLIT)
increment_split = PROFILE_INCREMENT_SPLITS.get(active.key, DEFAULT_INCREMENT_SPLIT)


def _split_text(split):
    """Formats a split dict as needs/wants/investment, e.g. ``50/25/25``."""
    return f"{split['needs']:.0f}/{split['wants']:.0f}/{split['investment']:.0f}"


st.caption(
    f"How income splits, derived from the plan. Your anchor year is {_split_text(base_split)} "
    f"(needs/wants/investment). After that only each year's raise splits "
    f"{_split_text(increment_split)}, so the investment slice keeps growing."
)
st.markdown(
    f"<div style='border-left:3px solid {NEEDS};background:var(--strip-bg);border-radius:4px;"
    f"padding:.5rem .8rem;color:var(--muted);font-size:{FS_BODY};margin:.2rem 0 .4rem'>"
    "These figures are <b>derived</b> — to change them, edit <b>Income</b>. The one "
    "thing to set here is your <b>target allocation</b> below.</div>",
    unsafe_allow_html=True,
)

if d.income[d.income["profile"] == active.key].empty:
    st.info("No income entered yet. Add it on the Income page.")
    st.stop()
income_years = compute.selectable_years(d.income, d.contributions, active.key)
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else income_years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", income_years, index=income_years.index(default_year))

HEADERS = {
    "year": "Year", "age": "Age", "total_income": "Income", "yoy": "YoY",
    "job_change": "Job change", "needs": "Needs", "wants": "Wants",
    "investment": "Investment", "monthly_needs": "Needs /mo",
    "monthly_wants": "Wants /mo", "monthly_investment": "Invest /mo",
    "cumulative_invested": "Cumulative",
}
MONEY = ["total_income", "needs", "wants", "investment", "monthly_needs",
         "monthly_wants", "monthly_investment", "cumulative_invested"]
FMT = {c: (lambda v: f"{v:,.0f}") for c in MONEY}
FMT["year"] = lambda v: f"{int(v)}"
FMT["age"] = lambda v: f"{int(v)}"
FMT["yoy"] = lambda v: "—" if v is None or pd.isna(v) else f"{v:+.0f}%"
FMT["job_change"] = lambda v: "Yes" if v else ""


def row_class(r):
    if r["is_projected"]:
        return "proj"
    return "cur" if int(r["year"]) == CURRENT_YEAR else ""


bs = compute.budget_series(active, d.income)
if bs.empty:  # income rows can exist yet all be zero — no earning year, no budget
    st.info("No earning year yet. Add income on the Income page.")
    st.stop()

# This year's monthly split first — the headline numbers.
row = bs[bs["year"] == year]
if not row.empty:
    r = row.iloc[0]
    pct = compute.split_pct(r)
    section(f"Monthly split · {year}")
    cols = st.columns(3)
    # Everything on this page is *plan*, so only the investment figure wears the
    # secondary (= planned) accent; needs/wants stay neutral.
    metric_tile(cols[0], "Needs", f"{inr_short(r['monthly_needs'])}/mo", f"{pct['needs']:.0f}% of income", big=True)
    metric_tile(cols[1], "Wants", f"{inr_short(r['monthly_wants'])}/mo", f"{pct['wants']:.0f}% of income", big=True)
    inv_sub = f"{pct['investment']:.0f}% of income"
    if year == CURRENT_YEAR:
        # The adjusted monthly: what to invest per remaining month to clear the
        # past shortfall AND finish this year's goal by December.
        year_goal = sum(compute.expected_contributions(active, d.income, d.targets, year).values())
        invested_ty = float(d.contributions.loc[
            (d.contributions["profile"] == active.key) & (d.contributions["year"] == year), "amount"
        ].sum())
        catch_up = compute.catch_up_amount(active, d.income, d.targets, d.contributions, year,
                                           flat_return=d.config.expected_return_pct)
        months_left = 13 - dt.date.today().month
        adj_monthly = (catch_up + max(0.0, year_goal - invested_ty)) / months_left
        inv_sub += f"<br>adjusted: {inr_short(adj_monthly)}/mo to be on track"
    metric_tile(cols[2], "Investment", f"{inr_short(r['monthly_investment'])}/mo", inv_sub,
                color=SECONDARY, big=True,
                help="The plan's monthly investment. 'Adjusted' spreads the past "
                     "shortfall plus what's left of this year's goal over the months "
                     "remaining, so following it makes you fully on track by December.")

# Target allocation lives here (moved from Actuals, 2026-07-20): right under
# the monthly split, so how each monthly goal is consumed per instrument reads
# top-down. The active mix is read-only; the editor sits in the expander.
budget_row = bs[bs["year"] == year]
investment = float(budget_row.iloc[0]["investment"]) if not budget_row.empty else 0.0
target = compute.resolve_target(active, d.targets, year)

section(f"Target allocation · how the monthly goal is consumed")
active_mix = pd.DataFrame({"category": list(target.keys()), "pct": list(target.values())})
active_mix = active_mix.sort_values("pct", ascending=False)
active_mix["per_year"] = active_mix["pct"] / 100 * investment
active_mix["per_month"] = active_mix["per_year"] / 12
html_table(
    active_mix,
    {"category": "Instrument", "pct": "Target %", "per_month": "₹ / month", "per_year": "₹ / year"},
    formats={"category": pretty_category, "pct": lambda v: f"{v:.0f}%",
             "per_year": inr_short, "per_month": inr_short},
)

with st.expander("Edit allocation"):
    st.caption("Set the % per instrument (must sum to 100). The ₹/year and ₹/month follow from that year's investment.")

    def derive_alloc(df):  # recompute the ₹ columns from the % column
        out = df.copy()
        out["per_year"] = out["pct"] / 100 * investment
        out["per_month"] = out["per_year"] / 12
        return out

    abase = f"alloc_{active.key}_{year}"
    agkey, avkey = f"{abase}__grid", f"{abase}__ver"
    if agkey not in st.session_state:
        g = pd.DataFrame({"category": d.config.categories})
        g["label"] = g["category"].map(pretty_category)
        g["pct"] = [target.get(c, 0.0) for c in d.config.categories]
        st.session_state[agkey] = derive_alloc(g[["label", "pct"]].assign(per_year=0.0, per_month=0.0))
        st.session_state[avkey] = 0

    alloc_edited = st.data_editor(
        st.session_state[agkey], hide_index=True, width="stretch",
        key=f"{abase}__{st.session_state[avkey]}",
        column_config={
            "label": st.column_config.TextColumn("Instrument", disabled=True),
            "pct": st.column_config.NumberColumn("Target %", min_value=0, max_value=100, required=True),
            "per_year": st.column_config.NumberColumn("₹ / year", disabled=True, format="localized"),
            "per_month": st.column_config.NumberColumn("₹ / month", disabled=True, format="localized"),
        },
    )
    resync(agkey, avkey, derive_alloc(alloc_edited), ["per_year", "per_month"])
    total_pct = alloc_edited["pct"].sum()
    ok = abs(total_pct - 100) < 0.01
    msg = f"Total <b>{total_pct:.0f}%</b>" + ("  ·  ready to save" if ok else "  ·  must sum to 100")
    st.markdown(f"<span style='color:{PRIMARY if ok else SECONDARY};font-weight:600'>{msg}</span>",
                unsafe_allow_html=True)

    seed_key = f"{abase}_seed"
    tmask = lambda df: (df["profile"] == active.key) & (df["year"] == year)
    seed_slice_sig(seed_key, slice_sig(d.targets[tmask(d.targets)], ["category", "pct"]))

    if st.button(f"Save {year}", key=f"save_alloc_{active.key}_{year}",
                 type="primary", disabled=not ok):
        try:
            # Fresh read so another year/person's targets aren't reverted, and a
            # stale guard for this exact profile+year.
            fresh = storage.load_targets(d.root, d.config, d.profiles)
            if stale_since_open(seed_key, slice_sig(fresh[tmask(fresh)], ["category", "pct"]),
                                f"{year}'s target allocation"):
                st.stop()
            rows = pd.DataFrame({"profile": active.key, "year": year,
                                 "category": d.config.categories, "pct": alloc_edited["pct"].values})
            rows = rows[rows["pct"] > 0]
            others = fresh[~tmask(fresh)]
            merged = pd.concat([others, rows], ignore_index=True)
            storage.validate_targets(merged, d.config, d.profiles)
            storage.save_targets(d.root, merged)
            st.session_state.pop(seed_key, None)
            del st.session_state[agkey]
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")
    st.caption("A saved year carries forward until you set a newer one.")

# Then the slice shifting over the actual years (100% stacked), with the
# investment segment labelled with both its % and the raw yearly rupees.
actual = bs[~bs["is_projected"]]
yr = actual["year"].astype(int).astype(str)
tot = actual["total_income"]
needs_p = (100 * actual["needs"] / tot).round(0)
wants_p = (100 * actual["wants"] / tot).round(0)
inv_p = (100 * actual["investment"] / tot).round(0)
inv_label = [f"{p:.0f}% · {inr_short(a)}" for p, a in zip(inv_p, actual["investment"])]
# Colour roles: the derived investment slice is *planned* money, so it wears
# the secondary accent; needs/wants are neutral grays (a category is not a role).
f = go.Figure()
f.add_bar(x=yr, y=needs_p, name="Needs", marker_color=NEEDS)
f.add_bar(x=yr, y=wants_p, name="Wants", marker_color=SAND)
f.add_bar(x=yr, y=inv_p, name="Investment", marker_color=SECONDARY,
          text=inv_label, textposition="inside",
          textfont=dict(color="white", size=11), insidetextanchor="middle")
f.update_layout(barmode="stack", xaxis=dict(type="category"), yaxis=dict(ticksuffix="%", range=[0, 100]))
style_fig(f, height=300)
chart_title("The investment slice, year by year (label shows % and ₹/yr invested)")
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

with st.expander("Full detail (all years + projections)"):
    st.caption("Current year highlighted; projected years in muted italics.")
    html_table(bs, HEADERS, formats=FMT, row_class=row_class)
