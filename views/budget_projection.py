import datetime as dt

import pandas as pd
import streamlit as st

import compute
import storage
from config import (
    DEFAULT_BASE_SPLIT, PROFILE_BASE_SPLITS,
)
from ui import (
    FS_BODY, NEEDS, accent_primary, accent_secondary,
    html_table, inr_short, load_all, metric_tile, page_header, pretty_category,
    resync, save_failed, saved, section, seed_slice_sig, slice_sig,
    stale_since_open,
)

CURRENT_YEAR = dt.date.today().year

d = load_all()
active = page_header("Budget", d.profiles, d.root)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
base_split = PROFILE_BASE_SPLITS.get(active.key, DEFAULT_BASE_SPLIT)
increment_split = compute.increment_split_for(active.key, CURRENT_YEAR)


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
    "These figures are <b>derived</b>. To change them, edit <b>Income</b>. The one "
    "thing to set here is your <b>target allocation</b> below.</div>",
    unsafe_allow_html=True,
)

if d.income[d.income["profile"] == active.key].empty:
    st.info("No income entered yet. Add it on the Income page.")
    st.stop()

HEADERS = {
    "year": "Year", "age": "Age", "total_income": "Income", "yoy": "YoY",
    "job_change": "Job change", "needs": "Needs", "wants": "Wants",
    "investment": "Investment", "monthly_needs": "Needs /mo",
    "monthly_wants": "Wants /mo", "monthly_investment": "Invest /mo",
    "cumulative_invested": "Cumulative",
}
MONEY = ["total_income", "needs", "wants", "investment", "monthly_needs",
         "monthly_wants", "monthly_investment", "cumulative_invested"]
FMT = {c: inr_short for c in MONEY}  # short ₹ keeps the 12 columns in bounds
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

# Budget over time, on top (as Income has): every year, actual and projected.
section("Budget over time")
html_table(bs, HEADERS, formats=FMT, row_class=row_class)
st.caption("Current year highlighted; projected years in muted italics.")

income_years = compute.selectable_years(d.income, d.contributions, active.key)
default_year = CURRENT_YEAR if CURRENT_YEAR in income_years else income_years[-1]
yc, _ = st.columns([1, 5])
year = yc.selectbox("Year", income_years, index=income_years.index(default_year))

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
        catch_up = compute.catch_up_amount(active, d.income, d.targets, d.contributions, year)
        left = max(0.0, year_goal - invested_ty)
        n = compute.months_left()
        adj_monthly = (left + catch_up) / n
        inv_sub += f"<br>to finish {year}: {inr_short(adj_monthly)}/mo, {compute.month_span()}"
        inv_help = (f"The plan's monthly investment. 'To finish {year}' = {inr_short(left)} left of "
                    f"{year}'s goal + {inr_short(catch_up)} past years' shortfall, spread over the "
                    f"{n} month{'s' if n != 1 else ''} left. Following it puts you fully on track by December.")
    else:
        inv_help = "The plan's monthly investment for this year."
    metric_tile(cols[2], "Investment", f"{inr_short(r['monthly_investment'])}/mo", inv_sub,
                color=SECONDARY, big=True, help=inv_help)

# Target allocation lives here (moved from Actuals, 2026-07-20): right under
# the monthly split, so how each monthly goal is consumed per instrument reads
# top-down. The active mix is read-only; the year-by-year plan below edits it.
budget_row = bs[bs["year"] == year]
investment = float(budget_row.iloc[0]["investment"]) if not budget_row.empty else 0.0
target = compute.resolve_target(active, d.targets, year)

section(f"Target allocation · how the monthly goal is consumed")
# Every instrument, in the same order as the Investments table, so the two
# pages line up row for row (0% included).
active_mix = pd.DataFrame({"category": d.config.categories,
                           "pct": [target.get(c, 0.0) for c in d.config.categories]})
active_mix["per_year"] = active_mix["pct"] / 100 * investment
active_mix["per_month"] = active_mix["per_year"] / 12
html_table(
    active_mix,
    {"category": "Instrument", "pct": "Target %", "per_month": "₹ / month", "per_year": "₹ / year"},
    formats={"category": pretty_category, "pct": lambda v: f"{v:g}%",
             "per_year": inr_short, "per_month": inr_short},
)

section("Allocation plan, year by year")
st.caption("Each row is one year's target mix and must add up to 100%. A year left the same "
           "as the one before simply carries it forward. Edit any year, then Save.")
cats = d.config.categories
plan_years = list(range(int(bs["year"].min()), CURRENT_YEAR + 5))
plan = compute.allocation_plan(active, d.targets, plan_years, cats)
labels = {c: pretty_category(c) for c in cats}


def with_total(df):  # the live Total column, recomputed from the % columns
    return df.assign(Total=df[cats].sum(axis=1))


pbase = f"plan_{active.key}"
pgkey, pvkey = f"{pbase}__grid", f"{pbase}__ver"
if pgkey not in st.session_state:
    st.session_state[pgkey] = with_total(plan[["year", *cats]])
    st.session_state[pvkey] = 0
plan_edited = st.data_editor(
    st.session_state[pgkey], hide_index=True, width="stretch",
    key=f"{pbase}__{st.session_state[pvkey]}",
    column_config={
        "year": st.column_config.NumberColumn("Year", disabled=True, format="%d"),
        **{c: st.column_config.NumberColumn(labels[c], min_value=0, max_value=100, format="%g%%")
           for c in cats},
        "Total": st.column_config.NumberColumn("Total", disabled=True, format="%g%%"),
    },
)
resync(pgkey, pvkey, with_total(plan_edited), ["Total"])
off = plan_edited[(plan_edited[cats].sum(axis=1) - 100).abs() >= 0.01]["year"].astype(int).tolist()
ok = not off
msg = ("Every year adds up to 100%  ·  ready to save" if ok
       else f"Must add up to 100%: {', '.join(map(str, off))}")
st.markdown(f"<span style='color:{PRIMARY if ok else SECONDARY};font-weight:600'>{msg}</span>",
            unsafe_allow_html=True)

seed_key = f"{pbase}_seed"
pmask = lambda df: df["profile"] == active.key
seed_slice_sig(seed_key, slice_sig(d.targets[pmask(d.targets)], ["year", "category", "pct"]))

if st.button("Save allocation plan", key=f"save_plan_{active.key}", type="primary", disabled=not ok):
    try:
        # Fresh read so the other person's targets aren't reverted, and a stale
        # guard on this person's whole plan.
        fresh = storage.load_targets(d.root, d.config, d.profiles)
        if stale_since_open(seed_key, slice_sig(fresh[pmask(fresh)], ["year", "category", "pct"]),
                            "the allocation plan"):
            st.stop()
        rows = compute.target_rows_from_plan(active, plan_edited, cats)
        merged = pd.concat([fresh[~pmask(fresh)], rows], ignore_index=True)
        storage.validate_targets(merged, d.config, d.profiles)
        storage.save_targets(d.root, merged)
        st.session_state.pop(seed_key, None)
        del st.session_state[pgkey]
        saved()
    except Exception as exc:
        save_failed(exc)
