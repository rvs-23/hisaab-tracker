import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import compute
import storage
from ui import (
    GRID, ON_TRACK_PCT, accent_primary, accent_secondary, chart_title, edit_card,
    html_table, inr_axis, inr_short, load_all, metric_tile, page_header,
    pretty_category, resync, section, style_fig,
)

d = load_all()
active = page_header("Actuals", d.profiles)
PRIMARY, SECONDARY = accent_primary(), accent_secondary()  # per-person colours
scope = [active.key]
st.caption("What actually went in, against the plan, per category; negative shortfall = under-invested.")

if d.income[d.income["profile"] == active.key].empty:
    st.info("No data yet — add income first.")
    st.stop()
years = compute.selectable_years(d.income, d.contributions, active.key)

contrib_years = sorted(
    d.contributions.loc[d.contributions["profile"] == active.key, "year"].dropna().astype(int).unique()
)
default = contrib_years[-1] if contrib_years else years[-1]
yc, _ = st.columns([1, 5])
year = int(yc.selectbox("Year", years, index=years.index(default)))

pva = compute.plan_vs_actual(active, d.income, d.targets, d.contributions, year)
emergency_fund = compute.emergency_fund_target(active, d.income, year)

if pva.empty:
    st.info("No plan for this selection/year yet.")
    st.stop()

# Graph first: planned vs actual per bucket.
chart_title(f"Planned vs actual, by bucket · {year}")
asc = pva.sort_values("expected")
f = go.Figure()
f.add_bar(y=[pretty_category(x) for x in asc["category"]], x=asc["expected"], name="Planned",
          orientation="h", marker_color=SECONDARY)
f.add_bar(y=[pretty_category(x) for x in asc["category"]], x=asc["actual"], name="Actual",
          orientation="h", marker_color=PRIMARY)
f.update_layout(barmode="group")
inr_axis(f, max(asc["expected"].max(), asc["actual"].max()), axis="x")
style_fig(f)
f.update_xaxes(showgrid=True, gridcolor=GRID)
f.update_yaxes(showgrid=False)
st.plotly_chart(f, width="stretch", config={"displayModeBar": False})

# The tile label must say which year the derived buffer really uses: with no
# budget row for the picked year, emergency_fund_target falls back to the
# latest earning year.
bs = compute.budget_series(active, d.income)
has_budget_row = not bs[(bs["year"] == year) & (~bs["is_projected"])].empty
ef_sub = f"4 months of {year} needs + wants" if has_budget_row else "4 months of latest year's needs + wants"
ef_actual = compute.emergency_fund_actual(d.adjustments, active.key)

goal_pct = compute.pct_goal_achieved(pva)
section(f"How {year} is tracking")
cols = st.columns(4)
metric_tile(cols[0], "Goal achieved", f"{goal_pct:.0f}%", f"of {year}'s plan",
            color=PRIMARY if goal_pct >= ON_TRACK_PCT else SECONDARY, big=True)
metric_tile(cols[1], "Invested", inr_short(pva["actual"].sum()),
            f"of {inr_short(pva['expected'].sum())} planned", big=True)
metric_tile(cols[2], "Emergency-fund goal", inr_short(emergency_fund), ef_sub, big=True,
            help="The target, derived from your budget: 4 months of that year's full "
                 "monthly spending (needs + wants). Enter what you actually hold below.")
metric_tile(cols[3], "Emergency fund held", inr_short(ef_actual),
            "not entered yet" if ef_actual == 0 else
            ("covers the goal" if ef_actual >= emergency_fund else f"{inr_short(emergency_fund - ef_actual)} short"),
            color=PRIMARY if ef_actual >= emergency_fund and ef_actual > 0 else None, big=True,
            help="What you actually hold as the emergency buffer (hand-entered, counted "
                 "in net worth as cash). Update it below when the fund changes.")

with st.expander("Update emergency fund"):
    st.caption("The cash/liquid buffer you actually hold. Audited like any other save.")
    new_ef = st.number_input("Emergency fund held (₹)", min_value=0, value=int(ef_actual),
                             step=10000, key=f"ef_{active.key}")
    if st.button("Save", key=f"save_ef_{active.key}", type="primary"):
        others = d.adjustments[
            ~((d.adjustments["profile"] == active.key) & (d.adjustments["field"] == "emergency_fund"))
        ]
        rows = pd.DataFrame([{"profile": active.key, "field": "emergency_fund", "value": new_ef}])
        rows = rows[rows["value"] > 0]  # zero means "nothing recorded"
        merged = pd.concat([others, rows], ignore_index=True)[storage.ADJUSTMENTS_COLUMNS]
        try:
            storage.validate_adjustments(merged, d.profiles)
            storage.save_adjustments(d.root, merged)
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")
st.write("")

ordered = pva.sort_values("expected", ascending=False)
html_table(
    ordered,
    {"category": "Category", "expected": "Planned", "actual": "Actual", "shortfall": "Shortfall / surplus"},
    formats={"category": pretty_category, "expected": inr_short, "actual": inr_short, "shortfall": inr_short},
)

# Target allocation: the active mix read-only up front, the editor tucked into
# an expander so filling in actuals stays this page's main job.
budget_row = bs[bs["year"] == year]
investment = float(budget_row.iloc[0]["investment"]) if not budget_row.empty else 0.0
target = compute.resolve_target(active, d.targets, year)

section("Target allocation")
active_mix = pd.DataFrame({"category": list(target.keys()), "pct": list(target.values())})
active_mix = active_mix.sort_values("pct", ascending=False)
active_mix["per_year"] = active_mix["pct"] / 100 * investment
active_mix["per_month"] = active_mix["per_year"] / 12
html_table(
    active_mix,
    {"category": "Instrument", "pct": "Target %", "per_year": "₹ / year", "per_month": "₹ / month"},
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
            "per_year": st.column_config.NumberColumn("₹ / year", disabled=True, format="%.0f"),
            "per_month": st.column_config.NumberColumn("₹ / month", disabled=True, format="%.0f"),
        },
    )
    resync(agkey, avkey, derive_alloc(alloc_edited), ["per_year", "per_month"])
    total_pct = alloc_edited["pct"].sum()
    ok = abs(total_pct - 100) < 0.01
    msg = f"Total <b>{total_pct:.0f}%</b>" + ("  ·  ready to save" if ok else "  ·  must sum to 100")
    st.markdown(f"<span style='color:{PRIMARY if ok else SECONDARY};font-weight:600'>{msg}</span>",
                unsafe_allow_html=True)

    if st.button(f"Save {year}", key=f"save_alloc_{active.key}_{year}",
                 type="primary", disabled=not ok):
        rows = pd.DataFrame({"profile": active.key, "year": year,
                             "category": d.config.categories, "pct": alloc_edited["pct"].values})
        rows = rows[rows["pct"] > 0]
        others = d.targets[~((d.targets["profile"] == active.key) & (d.targets["year"] == year))]
        merged = pd.concat([others, rows], ignore_index=True)
        try:
            storage.validate_targets(merged, d.config, d.profiles)
            storage.save_targets(d.root, merged)
            del st.session_state[agkey]
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")
    st.caption("A saved year carries forward until you set a newer one.")

section("Fill in")

with edit_card(f"Record what you actually invested in {year}"):
    st.caption("One row per instrument. Add rows as you invest; other years are untouched.")
    # Scoped like the rest of the page: this person, this year. The key carries
    # both, so pending edits can never leak across a profile or year switch.
    mine = d.contributions[
        (d.contributions["profile"] == active.key) & (d.contributions["year"] == year)
    ].drop(columns=["profile", "year"])
    edited = st.data_editor(
        mine.sort_values("category").reset_index(drop=True),
        num_rows="dynamic", hide_index=True, width="stretch",
        key=f"contrib_{active.key}_{year}",
        column_config={
            "category": st.column_config.SelectboxColumn("Category", options=d.config.categories, required=True),
            "amount": st.column_config.NumberColumn("Amount (₹)", required=True),
            "notes": "Notes",
        },
    )
    if st.button("Save contributions", type="primary"):
        try:
            # Everyone else's rows and this person's other years stay untouched.
            others = d.contributions[
                ~((d.contributions["profile"] == active.key) & (d.contributions["year"] == year))
            ]
            mine_now = edited.assign(profile=active.key, year=year)
            combined = pd.concat([others, mine_now], ignore_index=True)[storage.CONTRIB_COLUMNS]
            storage.validate_contributions(combined, d.config, d.profiles)
            storage.save_contributions(d.root, combined)
            st.success("Saved.")
            st.rerun()
        except Exception as exc:
            st.error(f"Not saved: {exc}")

st.caption("The emergency-fund goal above is derived from your budget (4 months of needs + wants); what you actually hold is entered in the expander above.")
